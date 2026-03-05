# Framework Documentation - Python Backend

## Documentation Sources

Official documentation for core Python frameworks referenced in Lintel's architecture.

---

## 1. LangGraph (DOCS-PY-01 to DOCS-PY-10)

### DOCS-PY-01: StateGraph API

LangGraph's `StateGraph` is the core orchestration primitive:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from operator import add

class ThreadState(TypedDict):
    thread_ref: str
    messages: Annotated[list, add]
    current_phase: str
    pending_approvals: list[str]

graph = StateGraph(ThreadState)
graph.add_node("ingest", ingest_event)
graph.add_node("route", route_intent)
graph.add_edge("ingest", "route")
graph.add_conditional_edges("route", decide_next, {
    "plan": "plan_work",
    "review": "review_agent",
    "close": END,
})
```

State is a TypedDict. Annotated fields with reducers (like `add`) merge parallel branch outputs.

### DOCS-PY-02: Human-in-the-Loop (interrupt)

```python
graph.add_node("approval_gate", check_approval)
app = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["approval_gate"],
)

# Resume after human approval:
app.invoke(None, config={"configurable": {"thread_id": thread_id}})
```

`interrupt_before` pauses execution before the named node. The graph resumes when `invoke` is called again with the same `thread_id`.

### DOCS-PY-03: Checkpointing with Postgres

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
    await checkpointer.setup()  # Creates tables on first run
    app = graph.compile(checkpointer=checkpointer)
    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "thread-123"}},
    )
```

Always pass `thread_id` in config. Call `setup()` at startup.

### DOCS-PY-04: Send API for Parallelism

```python
from langgraph.graph import Send

def fan_out_agents(state: ThreadState) -> list[Send]:
    return [
        Send("agent_step", {"role": role, "context": state["context"]})
        for role in state["required_roles"]
    ]

graph.add_conditional_edges("plan", fan_out_agents)
```

`Send` dispatches to the same node with different payloads. LangGraph executes these concurrently.

### DOCS-PY-05: Subgraphs

Subgraphs allow composition of complex workflows:

```python
inner = StateGraph(AgentState)
inner.add_node("think", think_step)
inner.add_node("act", act_step)
inner_app = inner.compile()

outer = StateGraph(ThreadState)
outer.add_node("agent", inner_app)
```

### DOCS-PY-06: State Schema Design

Best practices from LangGraph docs:
- Use TypedDict, not dataclass (serialization compatibility)
- Keep state flat where possible
- Use Annotated reducers for merge-on-parallel
- Avoid large objects in state (store references, not blobs)
- Schema changes require migration of checkpointed state

### DOCS-PY-07: Streaming

```python
async for event in app.astream_events(
    input_state,
    config={"configurable": {"thread_id": tid}},
    version="v2",
):
    kind = event["event"]
    if kind == "on_chat_model_stream":
        # Token-level streaming
        print(event["data"]["chunk"].content, end="")
```

### DOCS-PY-08: Tool Calling in LangGraph

```python
from langchain_core.tools import tool

@tool
def search_code(query: str) -> str:
    """Search the codebase for relevant code."""
    ...

# Bind tools to model
model = ChatAnthropic(model="claude-sonnet-4-20250514").bind_tools([search_code])
```

Tools are plain decorated functions. LangGraph handles tool call/result routing.

### DOCS-PY-09: Error Handling in Graphs

- Nodes can raise exceptions; uncaught exceptions halt the graph
- Use `retry_policy` on nodes for transient failures
- For graceful degradation, catch in node and update state with error info
- `interrupt_before` can serve as a recovery checkpoint

### DOCS-PY-10: Graph Visualization

```python
from langgraph.graph import StateGraph
graph = StateGraph(...)
# ... define nodes and edges
print(graph.compile().get_graph().draw_mermaid())
```

---

## 2. FastAPI (DOCS-PY-11 to DOCS-PY-17)

### DOCS-PY-11: Lifespan Context Manager

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create pools, setup checkpointer
    pool = await asyncpg.create_pool(dsn)
    yield {"db_pool": pool}
    # Shutdown: close pools
    await pool.close()

app = FastAPI(lifespan=lifespan)
```

### DOCS-PY-12: Dependency Injection

```python
from fastapi import Depends

async def get_event_store(request: Request) -> EventStore:
    return request.state.event_store

@app.post("/commands/thread")
async def handle_command(
    cmd: CreateThreadCommand,
    store: EventStore = Depends(get_event_store),
):
    ...
```

Protocol-based DI: define `EventStore` as a Protocol in contracts, inject concrete implementation.

### DOCS-PY-13: WebSocket for Real-Time Updates

```python
@app.websocket("/ws/threads/{thread_id}")
async def thread_updates(websocket: WebSocket, thread_id: str):
    await websocket.accept()
    async for event in subscribe_to_thread(thread_id):
        await websocket.send_json(event.dict())
```

### DOCS-PY-14: Middleware

```python
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
    token = correlation_id_var.set(correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    correlation_id_var.reset(token)
    return response
```

### DOCS-PY-15: Exception Handlers

```python
@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=422,
        content={"error": exc.__class__.__name__, "detail": str(exc)},
    )
```

### DOCS-PY-16: Presidio Async Wrapping

Presidio's `AnalyzerEngine.analyze()` is synchronous. Wrap for async:

```python
import asyncio
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()

async def analyze_pii(text: str, language: str = "en"):
    return await asyncio.to_thread(
        analyzer.analyze, text=text, language=language, entities=None
    )
```

### DOCS-PY-17: Pydantic Discriminated Unions for Events

```python
from pydantic import BaseModel, Field
from typing import Literal, Union, Annotated

class ThreadMessageReceived(BaseModel):
    event_type: Literal["ThreadMessageReceived"] = "ThreadMessageReceived"
    text: str
    sender_id: str

class PIIDetected(BaseModel):
    event_type: Literal["PIIDetected"] = "PIIDetected"
    entities: list[dict]

DomainEvent = Annotated[
    Union[ThreadMessageReceived, PIIDetected, ...],
    Field(discriminator="event_type"),
]
```

---

## 3. Infrastructure Libraries (DOCS-PY-18 to DOCS-PY-25)

### DOCS-PY-18: asyncpg Connection Pool

```python
import asyncpg

pool = await asyncpg.create_pool(
    dsn="postgresql://...",
    min_size=5,
    max_size=20,
    command_timeout=30,
)
async with pool.acquire() as conn:
    row = await conn.fetchrow("SELECT * FROM events WHERE event_id = $1", eid)
```

### DOCS-PY-19: SQLAlchemy 2.0 Async

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine("postgresql+asyncpg://...")
async_session = async_sessionmaker(engine, expire_on_commit=False)

async with async_session() as session:
    result = await session.execute(select(EventModel).where(...))
```

### DOCS-PY-20: structlog Configuration

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
```

### DOCS-PY-21: Pydantic v2 Model Config

```python
from pydantic import BaseModel, ConfigDict

class EventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    event_id: UUID
    event_type: str
    occurred_at: datetime
    payload: dict
```

Use `frozen=True` for immutable event models. Use `strict=True` to prevent type coercion.

### DOCS-PY-22: OpenTelemetry Setup

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("lintel")
```

### DOCS-PY-23: httpx Async Client

```python
import httpx

async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()
```

### DOCS-PY-24: tenacity Retry

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def call_model(prompt: str) -> str:
    ...
```

### DOCS-PY-25: pytest-asyncio Patterns

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url()

@pytest.fixture
async def event_store(postgres):
    store = PostgresEventStore(postgres)
    await store.setup()
    yield store
    await store.teardown()
```

---

## 4. Additional Framework Notes

### DOCS-PY-26: LangChain Structured Output

```python
from langchain_core.output_parsers import PydanticOutputParser

class TaskBreakdown(BaseModel):
    tasks: list[str]
    estimated_complexity: str

parser = PydanticOutputParser(pydantic_object=TaskBreakdown)
chain = prompt | model | parser
```

### DOCS-PY-27: litellm for Multi-Provider

```python
import litellm

response = await litellm.acompletion(
    model="anthropic/claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "..."}],
)
```

litellm provides a unified interface across 100+ LLM providers. Good fit for Lintel's model router.

### DOCS-PY-28: NATS.py Client

```python
import nats

nc = await nats.connect("nats://localhost:4222")
js = nc.jetstream()

# Publish
await js.publish("lintel.events.thread", payload)

# Subscribe with durable consumer
sub = await js.subscribe("lintel.events.>", durable="projection-worker")
async for msg in sub.messages:
    await process_event(msg)
    await msg.ack()
```

### DOCS-PY-29: Docker SDK for Python

```python
import docker

client = docker.from_env()
container = client.containers.run(
    "lintel-sandbox:latest",
    detach=True,
    mem_limit="4g",
    cpu_quota=200000,
    read_only=True,
    tmpfs={"/tmp": "size=1g"},
    network_mode="none",
    security_opt=["no-new-privileges"],
    cap_drop=["ALL"],
)
```

### DOCS-PY-30: Presidio Custom Recognizers

```python
from presidio_analyzer import Pattern, PatternRecognizer

api_key_recognizer = PatternRecognizer(
    supported_entity="API_KEY",
    patterns=[Pattern("api_key", r"sk-[a-zA-Z0-9]{32,}", 0.9)],
)
analyzer.registry.add_recognizer(api_key_recognizer)
```

### DOCS-PY-31: uv Package Manager

```bash
# Create project
uv init lintel
# Add dependencies
uv add fastapi uvicorn asyncpg langgraph presidio-analyzer
# Lock and sync
uv lock
uv sync
# Run
uv run uvicorn lintel.api.app:app
```

uv resolves dependencies 10-100x faster than pip. Native lockfile support.
