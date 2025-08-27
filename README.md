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

Deploying serverless
--------------------
- The FastAPI app can be adapted to AWS Lambda using `mangum` (see `backend/lambda_handler.py`). Note some gateways buffer streaming. For true streaming, consider:
  - Lambda Function URLs with streaming responses
  - Cloudfront + ALB + ECS/Fargate running Uvicorn/Gunicorn

Notes
-----
- Output is for demonstration only and is not legal advice.
- The backend returns `text/html` and streams within an `<article>` root so the UI displays progressively.
# test-contract-project
