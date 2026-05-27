import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field
from schemas import MemoryItem
from gateway import generate

MEMORY_FILE = Path("state/memory.json")

def _load_memory() -> List[MemoryItem]:
    if not MEMORY_FILE.exists():
        return []
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        return [MemoryItem.model_validate(item) for item in data]
    except Exception as e:
        print(f"[Memory Error] Could not load memory: {e}")
        return []

def _save_memory(items: List[MemoryItem]):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Using mode="json" ensures datetime serialization
    MEMORY_FILE.write_text(
        json.dumps([json.loads(item.model_dump_json()) for item in items], indent=2), 
        encoding="utf-8"
    )

class ExtractionItem(BaseModel):
    kind: str = Field(description="'fact' or 'preference'")
    keywords: List[str] = Field(description="A list of relevant keywords for search.")
    descriptor: str = Field(description="A complete, self-contained sentence describing the exact fact or preference (e.g. 'Claude Shannon was born on April 30, 1916').")
    value: dict = Field(description="Optional structured JSON data if applicable, otherwise an empty dictionary.")
    confidence: float = Field(description="A confidence score from 0.0 to 1.0.")

class ExtractionResult(BaseModel):
    items: List[ExtractionItem]

async def remember(query: str, ans: str, history: list, run_id: str) -> None:
    """
    Extracts structured fact/preference from the full conversation using the LLM and saves them.
    """
    prompt = f"""
    Review the following conversation holistically, which includes the user's initial query, the step-by-step history, and the final output given to the user.
    Extract the facts and preferences that can be stored and used to better assist the user in future conversations.
    
    CRITICAL RULES:
    1. TRANSIENT GOALS: DO NOT extract the surface-level task, question, or temporary goal. (e.g., Do NOT save "User asked for things to do in Tokyo" or "User wants to know about Claude Shannon").
    2. IMPLICIT PREFERENCES: DO analyze the query to extract underlying lifestyle clues or formatting habits. If the user asks for "family-friendly" activities or "numbered lists", infer and save that as a PREFERENCE (e.g., "User prefers family-friendly recommendations", "User prefers output formatted as short numbered lists").
    3. LEARNED FACTS: DO extract valuable, generalized world knowledge or insights that were generated in the final answer (e.g., "Python asyncio best practices include using asyncio.run()").
    4. PERSONAL FACTS: DO extract objective truths about the user's life or environment (e.g., "User's mother's birthday is May 15").
    5. EXPLICIT PREFERENCES: DO extract direct, stated rules the user wants you to follow forever (e.g., "Always use Python 3", "I prefer dark mode").
    
    If there are no explicit long-term facts or preferences to remember, you MUST return an empty list.
    
    User Query: "{query}"
    Final Answer Given: "{ans}"
    Conversation History: {json.dumps(history, indent=2)}
    """
    
    try:
        response = await generate(
            messages=[{"role": "user", "content": prompt}],
            provider="gl",
            temperature=0.1,
            response_format={
                "type": "json_schema",
                "schema": ExtractionResult.model_json_schema(),
                "name": "ExtractionResult",
                "strict": True
            }
        )
        
        if "parsed" in response and response["parsed"]:
            result_dict = response["parsed"]
            if isinstance(result_dict, str):
                result_dict = json.loads(result_dict)
        else:
            content = response.get("text")
            if not content:
                return
            result_dict = json.loads(content)
        parsed = ExtractionResult.model_validate(result_dict)
        
        memories = _load_memory()
        added = 0
        for item in parsed.items:
            # Only accept fact or preference
            if item.kind not in ["fact", "preference"]:
                continue
                
            mem_item = MemoryItem(
                id=f"mem_{uuid.uuid4().hex[:8]}",
                kind=item.kind, # type: ignore
                keywords=item.keywords,
                descriptor=item.descriptor,
                value=item.value,
                artifact_id=None,
                source="user_query",
                run_id=run_id,
                goal_id=None,
                confidence=item.confidence,
                created_at=datetime.now(timezone.utc)
            )
            memories.append(mem_item)
            added += 1
            
        if added > 0:
            _save_memory(memories)
            
    except Exception as e:
        print(f"[Memory Extraction Error] {e}")

def read(query: str, history: List[dict] = None) -> List[MemoryItem]:
    """
    Pure Python keyword-search over memory items.
    """
    memories = _load_memory()
    if not memories:
        return []
        
    query_lower = query.lower()
    
    results = []
    for item in memories:
        score = 0
        if item.descriptor.lower() in query_lower:
            score += 2
        for kw in item.keywords:
            if kw.lower() in query_lower:
                score += 1
                
        # To make "When is mom's birthday?" match "mom" and "birthday"
        # we can also check if keywords match words in the query
        query_words = set(query_lower.split())
        for kw in item.keywords:
            if kw.lower() in query_words:
                score += 1
                
        if score > 0:
            results.append((score, item))
            
    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in results]

async def extract_iteration_memory(
    query: str,
    goal_text: str,
    action_taken: str,
    outcome: dict,
    history: list[dict],
    run_id: str,
    goal_id: Optional[str] = None
) -> None:
    """
    Analyzes the outcome of an iteration and selectively stores facts and preferences.
    """
    prompt = f"""
    Analyze the following conversation history and the outcome of the latest iteration of a task.
    Extract ONLY long-term, durable facts or user preferences that were learned and are worth remembering permanently.
    
    CRITICAL RULES:
    1. DO NOT save the answer to the user's question, web search results, or raw data as a memory.
    2. DO NOT save the user's current task or goal as a memory. 
    3. FACT: Objective truths about the user's environment or technical setup (e.g. "User lives in New York", "User's project is in Python 3.12").
    4. PREFERENCE: Subjective choices or behavioral instructions for the agent (e.g. "User prefers concise answers", "User wants code in Rust").
    
    If there are no durable facts about the USER or their PREFERENCES, you MUST return an empty list.
    
    Overall Query: "{query}"
    Current Goal: "{goal_text}"
    Action Taken: "{action_taken}"
    Outcome/Result: {json.dumps(outcome)[:10000]}
    
    Full Conversation History so far:
    {json.dumps(history, indent=2)}
    """
    
    try:
        response = await generate(
            messages=[{"role": "user", "content": prompt}],
            provider="gl",
            temperature=0.1,
            response_format={
                "type": "json_schema",
                "schema": ExtractionResult.model_json_schema(),
                "name": "ExtractionResult",
                "strict": True
            }
        )
        
        if "parsed" in response and response["parsed"]:
            result_dict = response["parsed"]
            if isinstance(result_dict, str):
                result_dict = json.loads(result_dict)
        else:
            content = response.get("text")
            if not content:
                return
            result_dict = json.loads(content)
        parsed = ExtractionResult.model_validate(result_dict)
        
        memories = _load_memory()
        added = 0
        for item in parsed.items:
            if item.kind not in ["fact", "preference"]:
                continue
                
            mem_item = MemoryItem(
                id=f"mem_{uuid.uuid4().hex[:8]}",
                kind=item.kind, # type: ignore
                keywords=item.keywords,
                descriptor=item.descriptor,
                value=item.value,
                artifact_id=None,
                source="iteration_extraction",
                run_id=run_id,
                goal_id=goal_id,
                confidence=item.confidence,
                created_at=datetime.now(timezone.utc)
            )
            memories.append(mem_item)
            added += 1
            
        if added > 0:
            _save_memory(memories)
            print(f"[agent]         Iteration memory saved: {added} items.")
            
    except Exception as e:
        print(f"[Memory Extraction Error] {e}")
