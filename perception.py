import json
from typing import List
from gateway import generate
from schemas import Observation, Goal, MemoryItem

async def observe(query: str, history: List[dict], memory_hits: List[MemoryItem]) -> Observation:
    """
    Acts as the orchestrator. Reads history, memory hits, and query to decompose into goals.
    Tracks done status and attaches artifacts.
    """
    
    prompt = f"""
    You are the Perception Orchestrator. Break down the user query into logical goals using the context.

    # CONTEXT
    Query: {query}
    Memory: {json.dumps([json.loads(m.model_dump_json()) for m in memory_hits])}
    History: {json.dumps(history)}

    # INSTRUCTIONS
    1. Reason First: Briefly explain your step-by-step plan in the `reasoning` field.
    2. Reasoning Type: Categorize your thought process in `reasoning_type` (e.g., "logic_decomposition", "fallback").
    3. Goals vs. Logic: Keep goals strictly as tool-use directives; keep planning logic in `reasoning`.
    4. Conversation State: Review History. Mark previously completed goals as `done=True`.
    5. Artifact Attachments (CRITICAL): Review the History. If a past action resulted in an `artifact_id` (e.g., "art:xxx"), and your next open goal requires analyzing that data, you MUST copy that exact `artifact_id` into the `attach_artifact_id` field for that goal. Otherwise, the agent will lose the data and fetch it again in an endless loop!
    6. Self-Check: Ensure goals are sequential, non-redundant, and directly answer the query.
    7. Memory Handling: Do NOT create goals like "save to memory" or "remember this". Memory extraction happens automatically in the background after all goals are completed.
    8. Fallbacks: If unsure or a tool failed, output a fallback goal to ask for clarification.
    9. Strict Output: Output ONLY the expected JSON schema.
    """

    try:
        response = await generate(
            messages=[{"role": "user", "content": prompt}],
            auto_route="perception",
            temperature=1.0, # CRITICAL: Must use 1.0
            response_format={
                "type": "json_schema",
                "schema": Observation.model_json_schema(),
                "name": "Observation",
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
                return Observation(
                    reasoning="Failed to parse text, falling back.",
                    reasoning_type="fallback",
                    goals=[Goal(id="g1", text=query, done=False, attach_artifact_id=None)]
                )
            result_dict = json.loads(content)
        return Observation.model_validate(result_dict)
        
    except Exception as e:
        print(f"[Perception Error] {e}")
        # Fallback
        return Observation(
            reasoning=f"Exception encountered: {e}",
            reasoning_type="fallback",
            goals=[Goal(id="fallback", text=query, done=False, attach_artifact_id=None)]
        )
