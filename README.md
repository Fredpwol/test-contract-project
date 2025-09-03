AI Contract Generator
=====================

Overview
--------
Generate long-form Terms of Service using FastAPI + OpenAI with streaming to a React UI.

Architecture
------------
- Backend (`backend/`): FastAPI app organized into modules:
  - `app/app.py`: app factory and router registration
  - `app/routes/`: endpoint routers (`health`, `generate`, `session`, `chat`, `stream-test`)
  - `app/services/`: business logic (`generation`, `session`, `chat`)
  - `app/schemas.py`: Pydantic request models
  - `app/config.py`: environment-driven settings and prompt loader
  - `app/utils.py`: retries and streaming helpers
  - `prompts.yml` (in `backend/` root): all system/user/title prompts
- Frontend (`frontend/`): Vite/React TypeScript with reusable components:
  - `components/`: `SessionsList`, `ChatMessages`, `ChatInput`, `Viewer`

Environment
-----------
- Backend:
  - `OPENAI_API_KEY` (required)
  - `OPENAI_MODEL` (default `gpt-4o`)
  - `OPENAI_MAX_TOKENS` (default `16000`)
  - `prompts.yml` (optional): customize prompts without code changes
- Frontend:
  - `VITE_API_BASE_URL` (blank for same-origin/dev-proxy, set to deployed URL in prod)

Local development
-----------------
Backend
```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=YOUR_KEY
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend
```
cd frontend
npm install
npm run dev -- --host
```

Open `http://localhost:5173`. Dev proxy forwards `/api/*` to `http://localhost:8000`.

Testing
-------
```
cd backend
pip install -r requirements-dev.txt
pytest
```

Features
--------
- Streaming contract generation with retry/backoff.
- Session management with independent histories and metadata.
- Automatic session title generation on first prompt (editable inline).
- Prompts externalized to `backend/prompts.yml` for easy customization.

Tradeoffs & reasoning
---------------------
- Chose plain streaming over SSE to simplify infra and browser support; response is `text/html`
- `dangerouslySetInnerHTML` used for speed; sanitize upstream via model instruction and server control
- Retry/backoff at the backend to smooth transient model/provider failures
- Lambda adapter included, but best UX for streaming is containerized ASGI with keep-alive

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
