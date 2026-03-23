# Zetesis — Architecture Overview

Zetesis is a personal async research pipeline. You queue ideas, questions, and topics you want investigated; they get processed by LLMs running locally on your Mac Studio; and the results are presented for review in a web app.

## What It Does Today

**The core loop:** capture idea → queue → process → review → retain

1. **Submit** a research request via the web UI — a query with a type (deep dive, literature review, idea exploration, fact check), optional tags, context, and priority (0–10).
2. **Queue** — the request is persisted in PostgreSQL and picked up by a background worker in priority order. One request processes at a time.
3. **Inference** — an MLX backend loads a local Qwen 2.5-7B model, formats the query with a chat template and type-specific system prompt, and generates a response. Runs entirely on-device via Apple Silicon MPS.
4. **Review** — completed outputs appear in the Review tab. You can approve (moves to knowledge base), delete, add comments, or request a follow-up (re-queues a new request with the previous output as context, linked via `parent_id`).
5. **Knowledge base** — approved outputs are browsable in the Knowledge tab.

### Current capabilities

- 4 research request types, each with a tailored system prompt
- Priority queue backed by PostgreSQL (`FOR UPDATE SKIP LOCKED`) — no external broker
- Pluggable inference backend (registry pattern, currently MLX)
- Chat-template-formatted prompts (proper `<|im_start|>` formatting, not raw strings)
- Truncation detection — outputs that hit the token limit are flagged
- Crash recovery — requests stuck in `processing` are reset to `queued` on server restart
- Follow-up chains — follow-up requests carry the full previous output as context and link back to the original via `parent_id`
- Web UI (React + Tailwind) with 4 pages: Submit, Queue (with inline output expansion), Review, Knowledge
- Live badge counts on nav tabs (unchecked outputs, active queue items)
- Full validation: query length, priority bounds, type checking, unicode support

### Performance (Qwen 2.5-7B-4bit on M3 Ultra 96GB)

- ~125 tok/s generation throughput
- Typical response: 200–1000 tokens, 2–8 seconds
- 5.7s total queue overhead across 6 sequential requests
- Model loads in ~25s on first run (cached after that)

---

## System Architecture

```
┌─────────────────────────────┐
│     React PWA (:5173)       │
│  Submit │ Queue │ Review │  │
│         Knowledge           │
└────────────┬────────────────┘
             │ HTTP REST (proxied via Vite)
             ▼
┌─────────────────────────────┐
│    FastAPI Server (:8000)   │
│                             │
│  routes_requests   ── CRUD  │
│  routes_outputs    ── Read  │
│  routes_review     ── Act   │
│  routes_system     ── Health│
│                             │
│  InferenceWorker (async)    │
│    ↕ QueueManager           │
│    ↕ MLXBackend             │
└────────────┬────────────────┘
             │ asyncpg
             ▼
┌─────────────────────────────┐
│  PostgreSQL 16 + pgvector   │
│  requests │ outputs │reviews│
└─────────────────────────────┘
```

Everything runs in a single FastAPI process on one machine. The inference worker is an `asyncio.Task` started at boot. PostgreSQL runs in Docker. There are no microservices, no message brokers, and no external dependencies beyond the database.

---

## Monorepo Structure

```
zetesis/
├── packages/
│   ├── core/                   Shared domain models, enums, interfaces, config
│   │   └── zetesis_core/
│   │       ├── config.py       pydantic-settings (DATABASE_URL, model path, etc.)
│   │       ├── enums.py        RequestType, RequestStatus, OutputStatus, ReviewAction
│   │       ├── models.py       ResearchRequest, ResearchOutput, GenerationParams, etc.
│   │       └── interfaces.py   InferenceBackend ABC, BackendHealth
│   │
│   ├── server/                 FastAPI server, DB layer, queue, API routes
│   │   └── zetesis_server/
│   │       ├── main.py         App factory, lifespan (recovery + worker startup)
│   │       ├── api/
│   │       │   ├── schemas.py  Request/response Pydantic models
│   │       │   ├── routes_requests.py
│   │       │   ├── routes_outputs.py
│   │       │   ├── routes_review.py
│   │       │   └── routes_system.py
│   │       ├── db/
│   │       │   ├── models.py   SQLAlchemy ORM (RequestRow, OutputRow, ReviewRow)
│   │       │   ├── engine.py   Async engine + session factory
│   │       │   ├── repository.py  Data access layer
│   │       │   └── migrations/ Alembic (2 migrations: initial schema + truncated column)
│   │       └── queue/
│   │           ├── manager.py  PostgreSQL-backed priority queue + crash recovery
│   │           └── worker.py   Single-threaded async inference loop
│   │
│   ├── inference/              Pluggable inference backends
│   │   └── zetesis_inference/
│   │       ├── registry.py     BackendRegistry (decorator-based registration)
│   │       ├── mlx_backend.py  MLX implementation (chat template, run_in_executor)
│   │       └── prompt/
│   │           ├── templates.py  System prompts per request type
│   │           └── builder.py    build_messages() → [{role, content}, ...]
│   │
│   └── web/                    React + TypeScript + Vite + Tailwind
│       └── src/
│           ├── App.tsx         Tab navigation, badge counts (polls every 3s)
│           ├── api.ts          Typed API client
│           └── pages/
│               ├── SubmitPage.tsx     Form → POST /requests
│               ├── QueuePage.tsx      Live request list, inline output view
│               ├── ReviewPage.tsx     Approve/delete/comment/follow-up
│               └── KnowledgePage.tsx  Browse approved outputs
│
├── scripts/
│   ├── integration_test.py     84-assertion test suite
│   └── multi_request_test.py   Multi-request drain + priority ordering test
│
├── docker-compose.yml          PostgreSQL + pgvector
├── Makefile                    dev-db, dev-server, dev-web, migrate, test
└── pyproject.toml              uv workspace root
```

---

## Database Schema

Three tables. The `requests` table doubles as the work queue.

**requests** — research queries submitted by the user

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| query | TEXT | The research question |
| type | VARCHAR(50) | deep_dive, literature_review, idea_exploration, fact_check |
| tags | TEXT[] | GIN-indexed for fast filtering |
| context | TEXT | Optional background info |
| priority | INT | 0–10, higher = processed first |
| status | VARCHAR(20) | queued → processing → completed/failed |
| parent_id | UUID FK | Links follow-ups to their parent request |
| error | TEXT | Error message if failed |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

Queue index: `(priority DESC, created_at ASC) WHERE status = 'queued'`

**outputs** — LLM-generated responses

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| request_id | UUID FK | CASCADE delete with parent request |
| content | TEXT | The generated response (markdown) |
| model_id | VARCHAR(100) | e.g. `mlx-community/Qwen2.5-7B-Instruct-4bit` |
| status | VARCHAR(20) | unchecked → approved/deleted |
| inference_time_ms | INT | Wall-clock generation time |
| token_count | INT | Output token count |
| truncated | BOOL | True if output hit the max_tokens limit |
| embedding | Vector(1536) | pgvector column (not yet populated) |
| metadata | JSONB | Flexible storage for future use |
| created_at | TIMESTAMPTZ | |

**reviews** — audit trail of all review actions

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| output_id | UUID FK | CASCADE delete with parent output |
| action | VARCHAR(20) | approve, comment, follow_up, delete |
| comment | TEXT | User annotation |
| follow_up_request_id | UUID FK | Links to the new request if action=follow_up |
| created_at | TIMESTAMPTZ | |

---

## API Endpoints

All under `/api/v1`.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/requests` | Submit a research request |
| GET | `/requests` | List requests (filter by status, type; paginate) |
| GET | `/requests/{id}` | Get single request |
| DELETE | `/requests/{id}` | Cancel a queued request |
| GET | `/outputs` | List outputs (filter by status) |
| GET | `/outputs/{id}` | Get single output |
| POST | `/outputs/{id}/review` | Submit review action |
| GET | `/outputs/{id}/reviews` | List reviews for an output |
| GET | `/system/health` | DB connectivity check |
| GET | `/system/queue/status` | Queue counts by status |

Interactive docs at `/docs` (Swagger UI).

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single process | FastAPI + async worker in one process | One machine, one user, one GPU. No distribution problem to solve. |
| Queue in PostgreSQL | `FOR UPDATE SKIP LOCKED` on requests table | No need for Redis/RabbitMQ. Transactional, durable, zero extra infrastructure. |
| MLX for inference | Apple's native ML framework | Direct MPS access on Apple Silicon, unified memory, no CPU-GPU copies. |
| `run_in_executor` | Thread pool for blocking MLX calls | Keeps the FastAPI event loop responsive during generation. |
| Chat template | `tokenizer.apply_chat_template()` | Without it, the model was completing prompts instead of answering questions. Reduced output from ~4000 to ~500 tokens and fixed relevance. |
| Crash recovery | Reset `processing` → `queued` on startup | Prevents silent request loss after server crashes. |
| No SSE yet | Client-side polling (3s interval) | Simpler for MVP. PostgreSQL `LISTEN/NOTIFY` would eliminate this. |

---

## What's Missing — Future Integration Roadmap

### Near-term (high impact, moderate effort)

**Web search integration** — the model currently has no access to external information. Adding a search API (Brave, Tavily, SerpAPI) before inference would inject real-time context into the prompt. This is the single biggest quality improvement available.

**Per-request max_tokens** — currently hardcoded at 4096 for all request types. A "define X in one sentence" and a "write a full literature survey" get the same budget. Should be configurable per request, with sensible defaults per type.

**SSE / real-time push** — replace polling with Server-Sent Events. PostgreSQL `LISTEN/NOTIFY` can trigger pushes when outputs are created, eliminating the 3-second polling loop.

**Embedding generation** — the pgvector column exists but nothing writes to it. Running a small embedding model (e.g. `nomic-embed-text-v1.5`) after inference would enable semantic search across approved outputs.

**Semantic search endpoint** — `/knowledge/search?q=...` using pgvector cosine similarity over embeddings. The schema is ready; just needs the embedding pipeline and a query endpoint.

### Medium-term (architectural extensions)

**Multi-model support** — the `BackendRegistry` already supports multiple backends. Adding `llama.cpp`, OpenAI API, or Anthropic API backends would allow comparing outputs across models or routing by request type.

**Multi-agent patterns** — run the same query through multiple models or temperature settings and synthesize results. The follow-up chain mechanism already supports iterative refinement; a "council" pattern would parallelize it.

**Larger models** — the M3 Ultra 96GB can run Qwen 2.5-72B at 4-bit quantization (~40GB). This would dramatically improve output quality, especially for complex research questions.

**Dynamic batching** — group similar requests and process them in a single forward pass. Requires changes to the worker loop and MLX batch inference support.

**Retry logic and timeouts** — failed requests currently stay failed with no recovery path. Adding configurable retry counts with exponential backoff, plus a per-request timeout to prevent hung inference from blocking the queue.

### Longer-term (optimization and scale)

**KV cache compression** — quantized KV caches for efficient memory use during long-context generation. MLX supports `kv_bits` and `kv_group_size` parameters.

**Speculative decoding** — use a small draft model to propose tokens, verified by the main model. MLX's `stream_generate` already accepts a `draft_model` parameter.

**Linear probes for hallucination detection** — attach lightweight classifiers to intermediate model activations to flag low-confidence outputs.

**Token magnitude tracking** — log per-token probabilities as a proxy for model certainty, surfaced in the review UI.

**GraphRAG** — build a knowledge graph over approved outputs (entities, relationships, communities) for graph-augmented retrieval. Would require a graph layer (Neo4j or Apache AGE on PostgreSQL).

**Go/Rust migration paths** — Rust for custom MPS kernels and zero-copy token pipelines in the inference layer. Go for an API gateway if the server and inference engine are ever separated to different machines.

**Native iOS/macOS client** — Swift app for submitting and reviewing from the phone. The REST API is ready; this is purely a client-side effort.

**Hardware profiler** — auto-detect MPS memory bandwidth, available VRAM, and thermal state to dynamically adjust batch sizes and model quantization levels.

---

## Running Locally

```bash
# Prerequisites: Docker, Python 3.11+, Node.js, uv

# Start database
make dev-db

# Run migrations
make migrate

# Start API server (loads model on first request)
make dev-server

# Start web UI (separate terminal)
make dev-web

# Open http://localhost:5173
```

## Testing

```bash
# With the server running:
uv run python scripts/integration_test.py      # 84 assertions across 12 categories
uv run python scripts/multi_request_test.py     # Multi-request drain + priority test
```
