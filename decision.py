import json
from typing import List
from gateway import generate
from schemas import Goal, DecisionOutput, MemoryItem
import artifacts

async def next_step(
    query: str, 
    unfinished_goal: Goal, 
    history: List[dict], 
    memory_hits: List[MemoryItem],
    available_tools: List[dict]
) -> DecisionOutput:
    """
    Acts as the Selector. Looks at ONE unfinished goal and decides to answer or use a tool.
    """
    
    # Check if the goal has an attached artifact we should include in context
    artifact_content = ""
    if unfinished_goal.attach_artifact_id:
        try:
            raw_bytes = artifacts.get_bytes(unfinished_goal.attach_artifact_id)
            # Truncate if too long, let LLM read the top portion
            text = raw_bytes.decode('utf-8', errors='replace')
            artifact_content = f"\nAttached Artifact Content:\n{text[:15000]}\n[Truncated if longer]"
        except Exception as e:
            artifact_content = f"\n[Error loading attached artifact {unfinished_goal.attach_artifact_id}: {e}]"

    prompt = f"""
        You are the Decision Selector. Decide to answer or use a tool for the current goal.

        # CONTEXT
        Overall Query: {query}
        Current Unfinished Goal: {unfinished_goal.text}
        Available Tools: {json.dumps(available_tools)}
        Memory: {json.dumps([json.loads(m.model_dump_json()) for m in memory_hits])}
        History: {json.dumps(history)}
        {artifact_content}
        
        # INSTRUCTIONS
        1. Reason First: Briefly explain your step-by-step logic in `reasoning`.
        2. Reasoning Type: Categorize your thought process in `reasoning_type` (e.g., "tool_selection", "final_answer", "fallback").
        3. Tool vs Answer (MUTUALLY EXCLUSIVE):
        - If you need data or action to fulfill the goal, you MUST emit a `tool_call` and set `answer` to `null`. DO NOT guess.
        - If you have enough info in Context/History to fulfill the goal, provide a substantive `answer` and set `tool_call` to `null`.
        - Never provide both.
        4. Conversation State: Use History and Memory to inform your decision.
        5. Artifacts: NEVER pass artifact IDs (e.g., 'art:...') directly as arguments to tools. Tools do not know how to read them.
        6. Tool Arguments: When making a `tool_call`, you MUST populate its `arguments` field as a strictly serialized JSON string containing the exact parameters required by the tool's `inputSchema` (e.g., if the tool requires a 'url', you must include `'{{"url": "..."}}'` inside `arguments`). DO NOT leave `arguments` empty!
        7. Self-Check: Verify your chosen tool exists in Available Tools and arguments match its schema exactly.
        8. Fallbacks: If unsure or stuck in a loop, provide an `answer` asking the user for clarification.
        9. Strict Output: Output ONLY the expected JSON schema with exactly one action (tool OR answer).
        """

    try:
        response = await generate(
            messages=[{"role": "user", "content": prompt}],
            auto_route="decision",
            temperature=0.2,
            response_format={
                "type": "json_schema",
                "schema": DecisionOutput.model_json_schema(),
                "name": "DecisionOutput",
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
                return DecisionOutput(
                    reasoning="Failed to generate decision.",
                    reasoning_type="fallback",
                    answer="Failed to generate decision.",
                    tool_call=None
                )
            result_dict = json.loads(content)
        return DecisionOutput.model_validate(result_dict)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Decision Error] {e}")
        return DecisionOutput(
            reasoning=f"Error: {e}",
            reasoning_type="fallback",
            answer=f"Error in decision: {e}",
            tool_call=None
        )
