# EAGV3 Session 6 Multi-Agent Architecture

Learning project to build a Python-based multi-agent system from scratch without external orchestration frameworks. This project uses Pydantic for rigid communication schemas, `mcp` for standardized tooling, four distinct roles - Memory, Perception, Decision, and Action and a locally hosted LLM Gateway V3 for model routing.

## 🚀 Key Features
- **Four Distinct Roles:** Memory, Perception, Decision, and Action.
- **Durable Memory System:** Typed storage for long-term facts and short-term tool outcomes.
- **Content-Addressable Artifacts:** Secure handling of large tool outputs to prevent context explosion.
- **Deterministic Action Selection:** The Orchestrator sets goals, and the Selector resolves them one by one.
- **Model Context Protocol (MCP):** Standards-compliant tool execution.

## System Architecture

### 🧩 Core Components

The architecture operates across three distinct layers, communicating entirely through strictly-typed Pydantic models:

**1. Cognitive Layer**
*   **Perception (Orchestrator):** The planner. It breaks down the user query into discrete, manageable `Goal`s.
*   **Decision (Selector):** The decider. It looks at the current `Goal` and decides whether to emit a final answer or call a tool.
*   **Memory:** The historian. It handles extraction and durable storage of facts and tool outcomes.

**2. Execution Layer**
*   **Action (Dispatch):** The doer. It receives tool call requests and executes them against a standardized Model Context Protocol (MCP) server.

**3. Storage Layer**
*   **Memory DB:** JSON-based durable storage (`state/memory.json`).
*   **Artifacts:** Content-addressable storage for large tool outputs to prevent context window explosion (`state/artifacts/`).
*   **Logs:** Tracing of the agent's thought process (`logs/`).

### The Pydantic Handshake
- **MemoryItem:** Facts, preferences, tool outcomes.
- **Artifact:** Handle for raw bytes (`art:<hash>`).
- **Observation:** List of `Goal`s with `done` status.
- **DecisionOutput:** Either a final `answer` or a `tool_call`.

## How It Works

### 1. Initialization
The user issues a query. The agent initializes state and creates a timestamped run ID.

### 2. Memory Extraction
Before taking action, the `Memory` service evaluates the query using an LLM configured for extraction (`auto_route="memory"`). If the user states a fact (e.g., "My birthday is May 15"), it is saved to durable storage (`state/memory.json`).

### 3. The Multi-Agent Loop
The agent enters a `MAX_ITERATIONS` loop (default 15).

#### Step A: Perception (The Orchestrator)
- The Orchestrator receives the query, recent memory hits, and the action history.
- It breaks the problem into discrete `Goal`s.
- It assesses which goals are `done`.
- **Constraint:** Uses `temperature=1.0` to ensure diverse goal generation and prevent cyclical logic.

#### Step B: Decision (The Selector)
- The Selector receives the *first unfinished goal* and the list of available MCP tools.
- It decides whether it can generate a substantive answer or if it needs to emit a `tool_call`.
- **Safety:** It is strictly instructed never to pass `art:...` references to tools.

#### Step C: Action (The Dispatch)
- If the Selector chose a tool call, the `Action` module runs it via the local `mcp_server.py`.
- **Artifacts:** If a tool returns a massive payload (>4KB), the payload is hashed and written to disk (`state/artifacts/`). An `art:<hash>` handle is returned instead, protecting the LLM's context window.

#### Step D: Memory & Trace
- Tool outcomes are saved to memory.
- The entire state is appended to a JSON-L log file in `logs/` for tracing.


