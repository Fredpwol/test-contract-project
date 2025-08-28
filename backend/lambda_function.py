from mangum import Mangum
from main import app

# Create a reusable ASGI handler
_asgi_handler = Mangum(app)

def lambda_handler(event, context):
    return _asgi_handler(event, context)


