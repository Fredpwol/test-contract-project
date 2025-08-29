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

Run with Docker (local)
-----------------------
Prereqs: Docker Desktop

1) Build and start both services with compose:

```bash
docker compose up --build
```

2) Open the app at http://localhost:5173 (frontend) and the backend at http://localhost:8000.

Environment
-----------
- `OPENAI_API_KEY`: required (backend)
- `OPENAI_MODEL`: optional (default: `gpt-4o`)
- `OPENAI_MAX_TOKENS`: optional (default: `16000`)
- `CORS_ALLOW_ORIGINS`: CSV of allowed origins, or `*` (default)
- Frontend `VITE_API_BASE_URL`: base URL for backend (no trailing slash). Leave blank for same-origin or dev proxy; set to your Function URL/ALB when deployed.

Architecture
------------
- Frontend (Vite/React):
  - Textarea + inputs for optional `companyName`, `jurisdiction`, `tone`
  - Buttons: Generate, Abort, Copy, Download
  - Streams HTML using `fetch` + `ReadableStream`, progressively renders via `dangerouslySetInnerHTML`
  - Vite dev proxy forwards `/api/*` to backend
- Backend (FastAPI):
  - POST `/api/generate` streams Markdown (rendered on the client)
  - Retry policy with exponential backoff for model errors; token limit control via `OPENAI_MAX_TOKENS`
  - GET `/api/health`
  - Optional Lambda deployments: Function URL (recommended for streaming) or API Gateway (buffered; not recommended for streaming)

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
The app supports streaming. API Gateway buffers, so prefer one of:
- Lambda Function URL with Response Streaming (container image + AWS Lambda Web Adapter)
- ALB + ECS/Fargate (or EC2) running Uvicorn (HTTP/1.1) — best streaming UX

Build and push images to Amazon ECR
-----------------------------------
Use the helper script:

```bash
# Show options
./deploy.sh --help

# Backend only
./deploy.sh --component backend --backend-tag v1

# Frontend only
./deploy.sh --component frontend --frontend-tag v1

# Both (default)
./deploy.sh --component both

# If not already configured, pass region/account or export AWS_REGION
./deploy.sh --region us-east-1 --account-id 123456789012
```

The script:
- Ensures ECR repositories exist
- Logs in to ECR
- Builds with `docker buildx` (default `linux/amd64`) and pushes to ECR

ECS/Fargate (recommended for streaming)
--------------------------------------
1) Push backend and frontend images to ECR (see above)
2) Create an ECS Fargate cluster and two services (frontend, backend) or serve frontend via S3/CloudFront and run only backend on ECS
3) Create an ALB with listeners 80/443 → target group → backend service (port 8000)
4) Container command: `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --http h11`
5) Set env: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`, `CORS_ALLOW_ORIGINS`
6) Point frontend `VITE_API_BASE_URL` to the ALB DNS (no trailing slash)

Lambda (Function URL with AWS Lambda Web Adapter)
-------------------------------------------------
Example `backend/deploy.Dockerfile`:

```Dockerfile
FROM public.ecr.aws/awsguru/aws-lambda-adapter:0.9.4-python3.11
WORKDIR /var/task
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV AWS_LWA_READINESS_CHECK_PATH=/api/health \
    AWS_LWA_ENABLE_RESPONSE_STREAMING=true \
    PORT=8000
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000","--workers","1","--http","h11"]
```

Steps:
1) Build and push: `./deploy.sh --component backend --backend-dockerfile backend/deploy.Dockerfile`
2) Create Lambda from the image; set Timeout ≥ 60s; Memory ≥ 1024MB
3) Create a Function URL; set Invoke mode “Response streaming”
4) Update frontend `VITE_API_BASE_URL` to the Function URL
5) Test:

```bash
curl -i -N -H "Content-Type: application/json" \
  -d '{"prompt":"short test"}' \
  https://<function-url>/api/generate
```

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
- The backend streams Markdown; the frontend renders progressively.

Areas of Improvements
---------------------
- The AI Text generation can be broken down into sections and use a map reduce approach to iteratively build each section; inferering from the summarization of previous section. That way the model can generate more longer and cohesive document.
- Implement RAG based referencing for article citation to enable the reduction of hallucination in the model.
- Use diff text generation similar to cursor when editing the document which enables the following:
    1. Reduction of Token count when editing
    2. Keep relavant valid parts of the documents instead of rewriting everything from scratch
    3. Ease of rollback
- Execute in Background worker for long running text generation using reasoning models.

Repository hygiene
------------------
- `.gitignore` prevents committing build artifacts and secrets
- `.env.example` documents required environment variables
