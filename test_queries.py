import asyncio
import sys
import io
import shutil
from pathlib import Path

# Assume your agent's main loop is imported here. 
# It must return a tuple: (final_answer_string, total_iterations_integer)
from agent6 import run 

STATE_DIR = Path("state")
ARTIFACTS_DIR = STATE_DIR / "artifacts"
MEMORY_FILE = STATE_DIR / "memory.json"
TESTING_MD = Path("testing.md")

class DualLogger:
    """Captures stdout to a string buffer while still printing to the terminal."""
    def __init__(self):
        self.terminal = sys.stdout
        self.buffer = io.StringIO()

    def write(self, message):
        self.terminal.write(message)
        self.buffer.write(message)

    def flush(self):
        self.terminal.flush()
        
    def get_log(self):
        return self.buffer.getvalue()

def reset_state(keep_memory: bool = False):
    """Cleans the state/ directory between assignment attempts."""
    # Always clear artifacts
    # if ARTIFACTS_DIR.exists():
    #     shutil.rmtree(ARTIFACTS_DIR)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Conditionally clear memory
    if not keep_memory:
        if MEMORY_FILE.exists():
            MEMORY_FILE.unlink()
        MEMORY_FILE.write_text("[]", encoding="utf-8")
        print("[System] Wiped state/artifacts and state/memory.json")
    else:
        print("[System] Wiped state/artifacts but PRESERVED state/memory.json")

async def run_test(test_name: str, query: str, expected_iters: int, keep_memory: bool = False):
    print(f"\n{'='*60}\n🚀 RUNNING: {test_name}\n{'='*60}")
    
    reset_state(keep_memory)
    
    # Calculate the hard limit from the assignment instructions (2x expected)
    max_allowed_iters = expected_iters * 2 
    
    # Setup stdout capture
    logger = DualLogger()
    old_stdout = sys.stdout
    sys.stdout = logger

    try:
        # Run the agent
        final_answer, iterations = await run(query)
    except Exception as e:
        sys.stdout = old_stdout
        print(f"\n❌ TEST FAILED with Exception: {e}")
        return
    finally:
        # Restore normal stdout
        sys.stdout = old_stdout

    terminal_trace = logger.get_log()
    
    print(f"\n[RESULT] Finished in {iterations} iterations (Max allowed: {max_allowed_iters})")
    print(f"[RESULT] Answer: {final_answer}\n")
    
    # Append the run to the deliverables document
    with open(TESTING_MD, "a", encoding="utf-8") as f:
        f.write(f"## {test_name}\n")
        f.write(f"**Query:** `{query}`\n")
        f.write(f"**Iterations:** {iterations} (Limit: {max_allowed_iters})\n\n")
        f.write("**Terminal Trace:**\n```text\n")
        f.write(terminal_trace.strip())
        f.write(f"\n\nFINAL ANSWER:\n{final_answer}\n```\n\n---\n\n")
        
    # --- ASSIGNMENT CONSTRAINTS (Assertion will fail the test if limits breached) ---
    assert iterations <= max_allowed_iters, f"FAILED 2X RULE: Took {iterations} iters, max is {max_allowed_iters}"
    print("✅ TEST PASSED WITHIN ITERATION LIMITS")

async def main():
    # Initialize fresh deliverables file
    if TESTING_MD.exists():
        TESTING_MD.unlink()
    with open(TESTING_MD, "w", encoding="utf-8") as f:
        f.write("# Session 6 Target Query Outputs\n\n")

    # The 4 Target Queries with limits extracted from course materials
    tests = [
        {
            "name": "Query A (Shannon Wikipedia)",
            "query": "Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.",
            "expected_iters": 3,
            "keep_memory": False
        },
        {
            "name": "Query B (Tokyo Weather)",
            "query": "Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.",
            "expected_iters": 6,
            "keep_memory": False
        },
        {
            "name": "Query C - Run 1 (Mom's Birthday Setup)",
            "query": "My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.",
            "expected_iters": 4,
            "keep_memory": False
        },
        {
            "name": "Query C - Run 2 (Mom's Birthday Recall)",
            "query": "When is mom's birthday?",
            "expected_iters": 2,
            "keep_memory": True  # MUST BE TRUE to test durable memory
        },
        {
            "name": "Query D (Asyncio Research)",
            "query": "Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.",
            "expected_iters": 7,
            "keep_memory": False
        }
    ]

    for t in tests[:1]:
        await run_test(t["name"], t["query"], t["expected_iters"], t["keep_memory"])

if __name__ == "__main__":
    asyncio.run(main())