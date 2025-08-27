from mangum import Mangum
from main import app

# AWS Lambda entrypoint using API Gateway HTTP API. Note: API Gateway may buffer
# responses and not fully support streaming. For production streaming, consider
# Lambda Function URLs with streaming enabled or a containerized ASGI host.
handler = Mangum(app)

