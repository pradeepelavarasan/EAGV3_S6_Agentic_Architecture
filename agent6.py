import os
import json
from datetime import datetime
from dotenv import load_dotenv

import memory
import perception
import decision
import action
import artifacts

load_dotenv()
MAX_ITERATIONS = 15

async def run(query: str) -> tuple[str, int]:
    # Ensure logs dir
    os.makedirs("logs", exist_ok=True)
    session_log = f"logs/session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Session state
    history = []
    run_id = f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 2. Extract explicit memory
    await memory.remember(query, run_id)
    
    # Tools
    available_tools = await action.get_tools()
    
    for iter_count in range(1, MAX_ITERATIONS + 1):
        print(f"\n─── iter {iter_count} ───")
        
        # Memory hits
        hits = memory.read(query, history)
        print(f"[memory.read]   {len(hits)} hits")
        
        # Observe
        obs = await perception.observe(query, history, hits)
        for i, g in enumerate(obs.goals):
            status = "[done]" if g.done else "[open]"
            prefix = "[perception]    " if i == 0 else "                "
            print(f"{prefix}{status} {g.text}")
            if g.attach_artifact_id:
                print(f"                  attach={g.attach_artifact_id}")
                
        for g in obs.goals:
            if g.attach_artifact_id:
                try:
                    meta = artifacts.get_metadata(g.attach_artifact_id)
                    print(f"[attach]        {g.attach_artifact_id} ({meta.size_bytes} bytes)")
                except Exception:
                    print(f"[attach]        {g.attach_artifact_id} (unknown size)")
            
        if obs.all_done:
            print(f"\n[done] all {len(obs.goals)} goals satisfied\n")
            ans = "All goals completed."
            # Find the last answer in history if any
            for h in reversed(history):
                if h.get("action") == "answer":
                    ans = h.get("answer", ans)
                    break
            print(f"FINAL: {ans}")
            _write_log(session_log, iter_count, hits, obs, history, ans)
            return ans, iter_count
            
        next_goal = obs.next_unfinished()
        
        # Decision
        out = await decision.next_step(query, next_goal, history, hits, available_tools)
        
        if out.is_answer:
            print(f"[decision]      ANSWER: {out.answer}")
            
            # Failsafe: Abort early if the LLM gateway is down or hard errors occur
            if out.answer and out.answer.startswith("Error in decision:"):
                print("[agent]         Aborting early due to critical decision error.")
                return out.answer, iter_count
                
            history.append({
                "iteration": iter_count,
                "goal_id": next_goal.id,
                "action": "answer",
                "answer": out.answer
            })
            _write_log(session_log, iter_count, hits, obs, history, None)
            # Loop continues so perception can see the answer and mark done
            
        else:
            tc = out.tool_call
            print(f"[decision]      TOOL_CALL: {tc.name}({json.dumps(tc.arguments)})")
            
            # Action
            outcome, art_id = await action.execute(tc.name, tc.arguments)
            
            # Preview for terminal
            art_str = ""
            if art_id:
                try:
                    meta = artifacts.get_metadata(art_id)
                    art_str = f"[artifact {art_id}, {meta.size_bytes} bytes] "
                except:
                    art_str = f"[artifact {art_id}] "
            
            preview = ""
            if "result" in outcome:
                res = str(outcome["result"]).replace('\n', ' ')
                preview = "preview: " + res[:100] + "..." if len(res) > 100 else "preview: " + res
            elif "summary" in outcome:
                preview = "preview: " + str(outcome["summary"])
            elif "error" in outcome:
                preview = "error: " + str(outcome["error"])
                
            print(f"[action]        → {art_str}{preview}")
            
            # Record
            memory.record_outcome(run_id, next_goal.id, tc.name, outcome, art_id)
            
            history.append({
                "iteration": iter_count,
                "goal_id": next_goal.id,
                "action": "tool_call",
                "tool": tc.name,
                "arguments": tc.arguments,
                "outcome": outcome,
                "artifact_id": art_id
            })
            
            _write_log(session_log, iter_count, hits, obs, history, None)

    return "Max iterations reached.", MAX_ITERATIONS

def _write_log(log_file, iter_count, hits, obs, history, answer):
    with open(log_file, "a", encoding="utf-8") as f:
        log_entry = {
            "iteration": iter_count,
            "timestamp": datetime.now().isoformat(),
            "memory_hits": [json.loads(h.model_dump_json()) for h in hits],
            "observation": json.loads(obs.model_dump_json()),
            "history_snapshot": history,
            "answer": answer
        }
        f.write(json.dumps(log_entry, indent=2) + "\n---\n")
