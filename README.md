AI Contract Generator (MVP)
===========================

Stack
-----
- Backend: FastAPI (serverless-friendly), Streaming OpenAI Chat Completions
- Frontend: React + Vite + TypeScript, streaming HTML viewer

Quick start (local)
-------------------
1. Backend

```bash
cd /workspace/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=YOUR_KEY
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2. Frontend

```bash
cd /workspace/frontend
npm install
npm run dev -- --host
```

Open http://localhost:5173 and generate a Terms of Service. The dev proxy forwards `/api/*` to `http://localhost:8000`.

Environment
-----------
- `OPENAI_API_KEY`: required
- `OPENAI_MODEL`: optional (default: `gpt-4o-mini`)
- `OPENAI_MAX_TOKENS`: optional (default: `4000`)

Architecture
------------
- Frontend (Vite/React):
  - Textarea + inputs for optional `companyName`, `jurisdiction`, `tone`
  - Buttons: Generate, Abort, Copy, Download
  - Streams HTML using `fetch` + `ReadableStream`, progressively renders via `dangerouslySetInnerHTML`
  - Vite dev proxy forwards `/api/*` to backend
- Backend (FastAPI):
  - POST `/api/generate` streams a single `<article>` root, model output HTML only
  - Retry policy with exponential backoff for model errors; token limit control via `OPENAI_MAX_TOKENS`
  - GET `/api/health`
  - Optional `lambda_handler.py` for AWS Lambda via `mangum`

Testing strategy
----------------
- Unit tests for API endpoints with a dummy OpenAI client to simulate streaming
- Edge cases covered: health, successful stream envelope, error mapping readiness
- Run tests:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Deploying serverless
--------------------
- The FastAPI app can be adapted to AWS Lambda using `mangum` (see `backend/lambda_handler.py`). Note some gateways buffer streaming. For true streaming, consider:
  - Lambda Function URLs with streaming responses
  - Cloudfront + ALB + ECS/Fargate running Uvicorn/Gunicorn

Tradeoffs & reasoning
---------------------
- Chose plain streaming over SSE to simplify infra and browser support; response is `text/html`
- `dangerouslySetInnerHTML` used for speed; sanitize upstream via model instruction and server control
- Retry/backoff at the backend to smooth transient model/provider failures
- Lambda adapter included, but best UX for streaming is containerized ASGI with keep-alive

Hosted demo or local run
------------------------
- Hosted demo: not included in this repo. Follow local steps above.
- Ensure no secrets are committed; use `.env` locally and CI secrets in deployment.

Notes
-----
- Output is for demonstration only and is not legal advice.
- The backend returns `text/html` and streams within an `<article>` root so the UI displays progressively.

Repository hygiene
------------------
- `.gitignore` prevents committing build artifacts and secrets
- `.env.example` documents required environment variables
