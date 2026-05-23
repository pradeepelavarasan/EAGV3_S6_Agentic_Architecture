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
    keywords: List[str]
    descriptor: str
    value: dict
    confidence: float

class ExtractionResult(BaseModel):
    items: List[ExtractionItem]

async def remember(query: str, run_id: str) -> None:
    """
    Extracts structured fact/preference from the query using the LLM and saves them.
    """
    prompt = f"""
    Analyze the following user query and extract any explicit facts or preferences the user wants you to remember.
    If there are none, return an empty list.
    Query: "{query}"
    """
    
    try:
        response = await generate(
            messages=[{"role": "user", "content": prompt}],
            auto_route="memory",
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

def record_outcome(
    run_id: str, 
    goal_id: Optional[str], 
    tool_name: str, 
    outcome_dict: dict, 
    artifact_id: Optional[str] = None
):
    """
    Saves MCP results as a tool_outcome memory item.
    """
    memories = _load_memory()
    mem_item = MemoryItem(
        id=f"mem_{uuid.uuid4().hex[:8]}",
        kind="tool_outcome",
        keywords=[tool_name, "outcome"],
        descriptor=f"Outcome of {tool_name}",
        value=outcome_dict,
        artifact_id=artifact_id,
        source="mcp_server",
        run_id=run_id,
        goal_id=goal_id,
        confidence=1.0,
        created_at=datetime.now(timezone.utc)
    )
    memories.append(mem_item)
    _save_memory(memories)
