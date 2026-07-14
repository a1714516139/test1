"""REST API route handlers — all endpoints under /api/v1/."""
import hashlib
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.config import settings
from app.models.request import ExtractRequest, JDKeywordsRequest, ScoreRequest
from app.models.response import (
    APIResponse,
    HealthData,
    UploadData,
    ExtractData,
    JDKeywordsData,
    ScoreData,
    AnalyzeData,
)
from app.services.pdf_parser import parse_pdf, validate_pdf
from app.services.text_cleaner import clean_text
from app.services.extractor import extract_info
from app.services.scorer import score_basic, score_ai, extract_jd_keywords
from app.services.cache_service import cache_service
from app.utils.helpers import generate_request_id, timestamp_ms, logger

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ok(data=None, meta=None) -> dict:
    """Build a uniform success response."""
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": meta or {},
    }


def _error(message: str, status_code: int = 400) -> dict:
    """Build a uniform error response."""
    return {
        "success": False,
        "data": None,
        "error": message,
        "meta": {"status_code": status_code},
    }


def _make_resume_id(text: str) -> str:
    """Generate a deterministic resume ID from cleaned text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _score_cache_key(resume_id: str, jd_text: str) -> str:
    """Generate a cache key for scoring results."""
    jd_hash = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()[:12]
    return f"score:{resume_id}:{jd_hash}"


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
@router.get("/health")
async def health():
    """Health check endpoint."""
    return _ok(data={"status": "healthy", "version": "1.0.0"})


# ---------------------------------------------------------------------------
# POST /resume/upload
# ---------------------------------------------------------------------------
@router.post("/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Upload and parse a PDF resume.

    Accepts a single PDF file, validates it, extracts text,
    cleans/structures it, and returns a resume_id for downstream use.
    """
    t_start = timestamp_ms()

    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    # Validate file size
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB} MB",
        )

    # Validate it's a PDF
    try:
        validate_pdf(file_bytes, file.filename or "unknown.pdf")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Parse the PDF
    try:
        parsed = await parse_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected PDF parse error: {e}")
        raise HTTPException(status_code=500, detail="Internal error parsing PDF")

    # Clean the text
    cleaned = clean_text(parsed.raw_text)

    # Generate resume ID
    resume_id = _make_resume_id(cleaned)

    # Cache the parsed result
    await cache_service.set(
        f"resume:{resume_id}",
        {
            "resume_id": resume_id,
            "filename": file.filename,
            "page_count": parsed.page_count,
            "cleaned_text": cleaned,
        },
    )

    latency = timestamp_ms() - t_start

    upload_data = UploadData(
        resume_id=resume_id,
        filename=file.filename or "unknown.pdf",
        page_count=parsed.page_count,
        raw_text_length=len(parsed.raw_text),
        cleaned_text=cleaned,
    )

    return _ok(
        data=upload_data.model_dump(),
        meta={"request_id": generate_request_id(), "latency_ms": latency},
    )


# ---------------------------------------------------------------------------
# POST /resume/extract
# ---------------------------------------------------------------------------
@router.post("/resume/extract")
async def extract_resume_info(body: ExtractRequest):
    """Extract key information from resume text using AI.

    Accepts resume_id and cleaned text, returns structured
    information (name, phone, email, skills, education, etc.).
    """
    t_start = timestamp_ms()

    # Check cache
    cached = await cache_service.get(f"extract:{body.resume_id}")
    if cached:
        logger.info(f"Returning cached extraction for {body.resume_id}")
        cached["meta"] = {"request_id": generate_request_id(), "latency_ms": timestamp_ms() - t_start, "cached": True}
        return cached

    # Extract info
    extracted = await extract_info(body.resume_text)

    # Build response
    data = ExtractData(
        resume_id=body.resume_id,
        extracted=extracted,
    )

    result = _ok(
        data=data.model_dump(),
        meta={"request_id": generate_request_id(), "latency_ms": timestamp_ms() - t_start},
    )

    # Cache result
    await cache_service.set(f"extract:{body.resume_id}", result)

    return result


# ---------------------------------------------------------------------------
# POST /jd/extract-keywords
# ---------------------------------------------------------------------------
@router.post("/jd/extract-keywords")
async def extract_jd_keywords_route(body: JDKeywordsRequest):
    """Extract weighted keywords from a job description."""
    t_start = timestamp_ms()

    keywords = extract_jd_keywords(body.jd_text)

    return _ok(
        data={"keywords": keywords},
        meta={"request_id": generate_request_id(), "latency_ms": timestamp_ms() - t_start},
    )


# ---------------------------------------------------------------------------
# POST /resume/score
# ---------------------------------------------------------------------------
@router.post("/resume/score")
async def score_resume(body: ScoreRequest):
    """Score a resume against a job description.

    Modes:
    - "basic": Fast keyword overlap + rule-based scoring (no LLM)
    - "ai": LLM-powered precise scoring with analysis
    """
    t_start = timestamp_ms()

    # Check cache
    cache_key = _score_cache_key(body.resume_id, body.jd_text)
    cached = await cache_service.get(cache_key)
    if cached:
        logger.info(f"Returning cached score for {cache_key}")
        cached["meta"] = {"request_id": generate_request_id(), "latency_ms": timestamp_ms() - t_start, "cached": True}
        return cached

    # Score
    if body.mode == "ai":
        score_data = await score_ai(body.resume_text, body.jd_text)
    else:
        score_data = score_basic(body.resume_text, body.jd_text)

    score_data.resume_id = body.resume_id

    result = _ok(
        data=score_data.model_dump(),
        meta={"request_id": generate_request_id(), "latency_ms": timestamp_ms() - t_start, "mode": body.mode},
    )

    # Cache result
    await cache_service.set(cache_key, result)

    return result


# ---------------------------------------------------------------------------
# POST /resume/analyze (composite: upload + extract + score)
# ---------------------------------------------------------------------------
@router.post("/resume/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    jd_text: str = Form(default=""),
    mode: str = Form(default="basic"),
):
    """Composite endpoint: upload PDF, extract info, and score against JD.

    All-in-one convenience endpoint. If jd_text is provided, scoring
    is included. Otherwise only upload + extraction are performed.
    """
    t_start = timestamp_ms()

    # --- Step 1: Upload & Parse ---
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Max {settings.MAX_FILE_SIZE_MB} MB")

    validate_pdf(file_bytes, file.filename or "unknown.pdf")
    parsed = await parse_pdf(file_bytes)
    cleaned = clean_text(parsed.raw_text)
    resume_id = _make_resume_id(cleaned)

    # --- Step 2: Extract ---
    extracted = await extract_info(cleaned)

    # --- Step 3: Score (if JD provided) ---
    score_data = None
    if jd_text.strip():
        if mode == "ai":
            score_data = await score_ai(cleaned, jd_text)
        else:
            score_data = score_basic(cleaned, jd_text)
        score_data.resume_id = resume_id

    # --- Build response ---
    analyze_data = AnalyzeData(
        resume_id=resume_id,
        filename=file.filename or "unknown.pdf",
        page_count=parsed.page_count,
        cleaned_text=cleaned,
        extracted=extracted,
        score=score_data,
    )

    return _ok(
        data=analyze_data.model_dump(),
        meta={"request_id": generate_request_id(), "latency_ms": timestamp_ms() - t_start},
    )


# ---------------------------------------------------------------------------
# GET /resume/{resume_id}
# ---------------------------------------------------------------------------
@router.get("/resume/{resume_id}")
async def get_cached_resume(resume_id: str):
    """Retrieve a previously analyzed resume from cache.

    Requires Redis to be configured. Returns 404 if not found.
    """
    cached = await cache_service.get(f"resume:{resume_id}")
    if cached:
        return _ok(data=cached, meta={"cached": True})

    raise HTTPException(status_code=404, detail="Resume not found in cache")
