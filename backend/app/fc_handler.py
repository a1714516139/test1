"""Mangum adapter for Alibaba Cloud Function Compute."""
from mangum import Mangum
from app.main import app

handler = Mangum(app)
