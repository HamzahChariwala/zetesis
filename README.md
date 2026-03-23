# Zetesis

A personal async research pipeline for Apple Silicon. You queue ideas, questions, and topics you want investigated; they are processed by LLMs running entirely on-device via Apple's MLX framework; and the results are presented in a web UI for review and curation into a personal knowledge base.

The name is a rhetorical term for systematic inquiry.

---

## How It Works

**The core loop:** capture idea → queue → process → review → retain

1. **Submit** a research request — a query with a type (deep dive, literature review, idea exploration, fact check), optional tags, context, and priority (0–10).
2. **Queue** — the request is persisted in PostgreSQL and picked up by a background worker in priority order.
3. **Inference** — the MLX backend loads a local model, formats the query with a type-specific system prompt, and generates a response on-device.
4. **Review** — completed outputs appear in the Review tab. You can approve (moves to knowledge base), delete, add comments, or request a follow-up (re-queues a new request with the previous output as context).
5. **Knowledge base** — approved outputs are browsable and semantically searchable.

Everything runs in a single process on one machine. No external APIs, no cloud, no message brokers beyond the database.

---

## Prerequisites

- macOS with Apple Silicon (tested on M3 Ultra 96GB)
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Node.js 20+
- Docker (for PostgreSQL)

---

## Setup

```bash
# Clone and enter the repo
git clone https://github.com/quixotry/zetesis.git
cd zetesis

# Copy and configure environment variables
cp .env.example .env

# Start the database
make dev-db

# Run migrations
make migrate

# Start the API server (loads model on first request)
make dev-server

# In a separate terminal, start the web UI
make dev-web
```

Open [http://localhost:5173](http://localhost:5173).

The first request will trigger model download and load (~25s after that is cached).

---

## Configuration

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://zetesis:zetesis_dev@localhost:5432/zetesis` | PostgreSQL connection string |
| `INFERENCE_BACKEND` | `mlx` | Backend to use (currently only `mlx`) |
| `INFERENCE_MODEL` | `mlx-community/Qwen2.5-7B-Instruct-4bit` | Default model |
| `SERVER_HOST` | `0.0.0.0` | API server bind address |
| `SERVER_PORT` | `8000` | API server port |
| `HF_TOKEN` | — | HuggingFace token (for gated models) |
| `BRAVE_SEARCH_API_KEY` | — | Enables the `web_search` tool |

Models can also be switched per-request from the Submit page. Available models (downloadable in-app):

| Model | Size |
|-------|------|
| Qwen 2.5 7B 4-bit | ~4 GB |
| Qwen 2.5 32B 4-bit | ~18 GB |
| Qwen 2.5 72B 4-bit | ~40 GB |
| Qwen 3 32B 4-bit | ~18 GB |
| Qwen 3.5 27B 4-bit | ~15 GB |

---

## Agentic Tools

Each request can optionally enable tools, selected per-request in the Submit page:

- **web_search** — queries the Brave Search API and injects results into the prompt (requires `BRAVE_SEARCH_API_KEY`)
- **knowledge_search** — semantic search over your approved outputs via pgvector embeddings

The worker runs up to 5 tool-calling rounds before forcing a final answer.

---

## Package Structure

```
packages/
  core/           Shared domain models, enums, interfaces, config (zetesis-core)
  inference/      Pluggable inference backends, prompt builder, tool executors (zetesis-inference)
  server/         FastAPI server, PostgreSQL-backed queue, API routes, embedding service (zetesis-server)
  web/            React 19 + TypeScript + Vite + Tailwind 4 frontend
scripts/
  integration_test.py     84-assertion test suite across 12 categories
  multi_request_test.py   Multi-request drain and priority ordering test
  backfill_embeddings.py  One-off script to backfill embeddings on existing outputs
```

---

## API

All endpoints are under `/api/v1`. Interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/requests` | Submit a research request |
| GET | `/requests` | List requests (filter by status, type) |
| GET | `/requests/{id}` | Get a single request |
| DELETE | `/requests/{id}` | Cancel a queued request |
| POST | `/requests/{id}/retry` | Retry a failed request |
| GET | `/outputs` | List outputs (filter by status) |
| GET | `/outputs/{id}` | Get a single output |
| PATCH | `/outputs/{id}/rate` | Rate an output (1–5) |
| POST | `/outputs/{id}/review` | Submit a review action (approve/delete/comment/follow_up) |
| GET | `/outputs/{id}/reviews` | List reviews for an output |
| GET | `/knowledge/search` | Semantic search over approved outputs |
| GET | `/knowledge/{id}/similar` | Find outputs similar to a given output |
| GET | `/system/health` | Database connectivity check |
| GET | `/system/queue/status` | Queue counts by status |
| GET | `/system/models` | List available models with download status |
| POST | `/system/models/download` | Download a model in the background |
| GET | `/system/tools` | List available tools |

---

## Testing

With the server running:

```bash
uv run python scripts/integration_test.py      # 84 assertions across 12 categories
uv run python scripts/multi_request_test.py     # Multi-request drain + priority ordering
```

---

## Performance

Measured on Qwen 2.5-7B-4bit, M3 Ultra 96GB:

- ~125 tok/s generation throughput
- Typical response: 200–1000 tokens, 2–8 seconds
- Model load: ~25s on first run, instant after cache

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed breakdown of the system design, database schema, key design decisions, and the future roadmap.
