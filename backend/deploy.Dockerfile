# backend/Dockerfile (Lambda image + Web Adapter, supports streaming)
FROM public.ecr.aws/lambda/python:3.11

# Install app deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add AWS Lambda Web Adapter (extension)
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter
RUN chmod +x /opt/extensions/lambda-adapter

# App code
COPY . .

# Adapter config
ENV AWS_LWA_READINESS_CHECK_PATH=/api/health
ENV AWS_LWA_ENABLE_RESPONSE_STREAMING=true
ENV PORT=8000

# Run FastAPI under uvicorn (HTTP/1.1, single worker)
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000","--workers","1","--http","h11"]