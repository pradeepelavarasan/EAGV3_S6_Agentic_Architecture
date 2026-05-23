# 🤖 MASTER PLAN: EAGV3 Session 6 Multi-Agent Architecture

**CONTEXT FOR THE AI CODING AGENT:** You are generating a complete Python project based on a specific architecture taught in EAGV3 Session 6. Do not use frameworks like LangChain, CrewAI, or AutoGen. Build this from scratch using `uv`, standard Python `asyncio`, and `pydantic`.

---

## 1. Core Architecture & Philosophy
The system replaces a monolithic agent loop with four distinct cognitive roles communicating strictly via Pydantic models. 
1. **Memory:** A typed service for reading/writing long-term facts, preferences, and short-term tool outcomes.
2. **Perception:** The orchestrator. Reads history, decomposes queries into goals, tracks `done` status, and attaches artifacts.
3. **Decision:** The selector. Looks at *one* unfinished goal at a time and decides to either return a final `answer` or emit a `tool_call`.
4. **Action:** Pure execution. Runs the MCP tool. Handles large payload sandboxing. No LLMs used here.

---

## 2. Strict Project Rules & Custom Guidelines
* **Dependency Management:** Use `uv` exclusively (`uv init`, `uv add pydantic httpx python-dotenv mcp mcp[cli]`).
* **LLM Gateway Integration:** All LLM calls MUST route through the local V3 Gateway at `http://localhost:8101/v1/chat/completions`.
  * *Gateway Path:* `/Users/pradeep/Library/CloudStorage/OneDrive-Personal/ML/2026 ML Projects/llm_gatewayV3`
  * *Routing:* Use `auto_route="decision"`, `auto_route="memory"`. 
  * *Perception Override:* For the Perception agent, use `provider="gf"` or `provider="gl"`. **CRITICAL:** You MUST pass `temperature=1.0` for Perception calls to prevent internal looping (as strictly mandated by the assignment).
* **Timestamped Logging:** Every iteration of the agent loop must be logged with a stack trace/state snapshot to `logs/session_YYYYMMDD_HHMMSS.log`.
* **Testing:** Create an automated `test_queries.py` script. The results must be saved to `testing.md`.

---

## 3. Project Setup & Directory Structure
```text
├── state/                  # Ignored in .gitignore
│   ├── memory.json         # Durable storage for Memory items
│   └── artifacts/          # Content-addressable raw bytes (.bin/.json)
├── logs/                   # For timestamped run traces
├── .env                    # API keys (Tavily, LLM providers, etc.)
├── .gitignore              # Ignore state/, logs/, sandbox/, .env
├── schemas.py              # Pydantic contracts
├── memory.py               # Memory service (read/write/record)
├── artifacts.py            # Artifact store (put/get_bytes)
├── gateway.py              # HTTP client to talk to LLM Gateway V3
├── perception.py           # Orchestrator role
├── decision.py             # Decision role
├── action.py               # Action role (MCP dispatch)
├── agent6.py               # The main loop (MAX_ITERATIONS = 15)
├── mcp_server.py           # (Provided) MCP Server with 9 tools
├── test_queries.py         # Automated execution of the 4 queries
├── testing.md              # Automated test results persistence
└── README.md               # Assignment deliverables
```

---

## 4. The Pydantic Contracts (`schemas.py`)
*CRITICAL:* Do not deviate from these shapes.

```python
from pydantic import BaseModel
from typing import Literal, Optional, List
from datetime import datetime

class MemoryItem(BaseModel):
    id: str
    kind: Literal["fact", "preference", "tool_outcome", "scratchpad"]
    keywords: List[str]
    descriptor: str
    value: dict
    artifact_id: Optional[str]
    source: str
    run_id: str
    goal_id: Optional[str]
    confidence: float
    created_at: datetime

class Artifact(BaseModel):
    id: str  # Format: "art:<sha256-prefix>"
    content_type: str
    size_bytes: int
    source: str
    descriptor: str

class Goal(BaseModel):
    id: str
    text: str
    done: bool
    attach_artifact_id: Optional[str]

class Observation(BaseModel):
    goals: List[Goal]
    
    @property
    def all_done(self) -> bool:
        return all(g.done for g in self.goals)
        
    def next_unfinished(self) -> Optional[Goal]:
        return next((g for g in self.goals if not g.done), None)

class ToolCall(BaseModel):
    name: str
    arguments: dict

class DecisionOutput(BaseModel):
    answer: Optional[str]
    tool_call: Optional[ToolCall]
    
    @property
    def is_answer(self) -> bool:
        return self.answer is not None
```

---

## 5. File-by-File Implementation Spec

### `artifacts.py`
* **Logic:** `put(blob)` hashes the blob, saves raw bytes to `state/artifacts/<hash>.bin` and metadata to `<hash>.json`. Returns `art:<hash>`.

### `memory.py`
* **Logic:** `remember(query)` extracts structured `fact`/`preference`. `read(query, history)` uses pure Python keyword-search. `record_outcome()` saves MCP results. Maps to `state/memory.json`.

### `perception.py` (The Orchestrator)
* **LLM Call:** Pinned to `provider="gf"` or `"gl"`. **MUST use `temperature=1.0`.**
* **Logic:** Identifies goals by list position. Uses integer indexing for artifacts. Force-attaches recent artifacts for synthesis goals.

### `decision.py` (The Selector)
* **LLM Call:** Routed via `auto_route="decision"`.
* **Logic:** Must answer substantively (3+ sentences). *Safety Guard:* Instruct model not to pass `art:...` handles to tools.

### `action.py` (Pure Dispatch)
* **Logic:** Dispatches to `mcp_server.py`. *Safety Guard:* Blocks `art:...` arguments. >4KB outputs go to `artifacts.put()`.

### `agent6.py` (The Main Loop)
1. Initialize `uv`, load `.env`. Set `MAX_ITERATIONS = 15`.
2. `memory.remember(query)`
3. `for iter in range(1, MAX_ITERATIONS + 1):`
   * `hits = memory.read(...)`
   * `obs = perception.observe(...)`
   * Check `obs.all_done`.
   * `out = decision.next_step(...)`
   * If answer, append history. Else `action.execute(...)`, record, append history.
   * **Write state to `logs/session_...log`.**
4. The function must return both the `final_answer` AND the `iteration_count` so the test script can assert limits.

### `test_queries.py` (Automated Test Suite)
This file must be explicitly written to execute the four target queries sequentially, enforce iteration limits, and manage state hygiene.
* **Logic Structure:**
  1. Define `reset_state(keep_memory=False)`: Uses `shutil` and `pathlib` to wipe `state/artifacts/` and `state/memory.json`.
  2. Define an `async def run_test(name, query, expected_max_iters, keep_memory)`:
     * Calls `reset_state()` if `keep_memory` is False.
     * Captures `sys.stdout` to capture the role-based bracket printing.
     * Awaits `agent6.run(query)`.
     * **CRITICAL:** `assert iterations <= expected_max_iters`.
     * Appends the captured terminal trace to `testing.md`.
  3. Execute the 4 required queries with these exact hard limits:
     * **Query A (Shannon):** `expected_max_iters=6`, `keep_memory=False`
     * **Query B (Tokyo):** `expected_max_iters=12`, `keep_memory=False`
     * **Query C Run 1 (Mom Bday Setup):** `expected_max_iters=8`, `keep_memory=False`
     * **Query C Run 2 (Mom Bday Recall):** `expected_max_iters=4`, **`keep_memory=True`**
     * **Query D (Asyncio):** `expected_max_iters=14`, `keep_memory=False`

---

## 6. Expected Terminal Format
The agent loop (`agent6.py`) must `print` its progression using the exact format below so it is captured by `test_queries.py`:

```text
─── iter 1 ───
[memory.read]   1 hits
[perception]    [open] Fetch the Wikipedia page for Claude Shannon
                [open] Extract birth date, death date, and three contributions
[decision]      TOOL_CALL: fetch_url({"url": "https://en.wikipedia.org/wiki/Claude_Shannon"})
[action]        → [artifact art:09ff0a67fe264eb9, 263065 bytes] preview: ...
```
