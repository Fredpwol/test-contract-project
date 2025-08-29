# backend/Dockerfile (Lambda image + Web Adapter, supports streaming)
FROM public.ecr.aws/docker/library/python:3.12.0-slim-bullseye

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Web Adapter config
ENV AWS_LWA_READINESS_CHECK_PATH=/api/health
ENV AWS_LWA_ENABLE_RESPONSE_STREAMING=true
ENV PORT=8000

# Run FastAPI with HTTP/1.1 and single worker
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000","--workers","1","--http","h11"]