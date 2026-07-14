"""Shared utilities: logging, request IDs, timing."""
import time
import uuid
import logging

logger = logging.getLogger("resume-analyzer")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)


def generate_request_id() -> str:
    return uuid.uuid4().hex[:12]


def timestamp_ms() -> int:
    return int(time.time() * 1000)
