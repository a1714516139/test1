"""Resume key information extraction using LLM + regex fallback."""
import re
import json
from typing import Optional
from app.services.llm_service import llm_service
from app.models.response import ExtractedInfo
from app.utils.helpers import logger

# ---------------------------------------------------------------------------
# LLM System Prompt for extraction
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM_PROMPT = """You are a professional resume parser. Your task is to extract structured information from resume text.

You MUST return ONLY a valid JSON object. No markdown, no explanation, no code fences.

The JSON object must follow this exact schema:
{
  "name": "full name or null",
  "phone": "phone number or null",
  "email": "email address or null",
  "address": "physical address or null",
  "job_intent": "desired job title / career objective or null",
  "expected_salary": "expected salary range or null",
  "work_years": <integer years of experience or null>,
  "education": [
    {"degree": "Bachelor/Master/PhD", "major": "major name", "school": "school name", "year": <graduation year or null>}
  ],
  "skills": ["skill1", "skill2", ...],
  "project_experience": [
    {"name": "project name", "role": "role in project", "description": "brief description", "duration_months": <number or null>}
  ],
  "languages": ["language1", "language2", ...],
  "certifications": ["cert1", "cert2", ...]
}

Rules:
- Leave fields as null or empty arrays if information is not found
- For work_years, infer from work experience descriptions if not explicitly stated
- For phone and email, use standard formats
- Extract all technical skills mentioned (programming languages, frameworks, tools)
- Keep descriptions concise (1-2 sentences max)
- If the resume is in Chinese, translate extracted values to English where appropriate but keep names in original language
"""

EXTRACTION_USER_PROMPT = """Please extract structured information from the following resume text:

{resume_text}"""


# ---------------------------------------------------------------------------
# Regex fallback patterns
# ---------------------------------------------------------------------------
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERNS = [
    re.compile(r"(?:\+?86[\s-]?)?1[3-9]\d{9}"),  # Chinese mobile
    re.compile(r"\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{6,10}"),  # International
    re.compile(r"\d{3}[\s-]?\d{3}[\s-]?\d{4}"),  # US/Canada
]


async def extract_info(resume_text: str) -> ExtractedInfo:
    """Extract structured info from resume text using LLM.

    Falls back to regex extraction if LLM call fails.

    Args:
        resume_text: Cleaned resume text.

    Returns:
        ExtractedInfo with structured fields populated.
    """
    # Try LLM extraction
    try:
        prompt = EXTRACTION_USER_PROMPT.format(resume_text=resume_text[:8000])
        result_dict = await llm_service.chat_json(
            prompt=prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.2,
        )
        logger.info("LLM extraction succeeded")
        return _parse_llm_result(result_dict)

    except Exception as e:
        logger.warning(f"LLM extraction failed, using regex fallback: {e}")
        return _regex_fallback(resume_text)


def _parse_llm_result(data: dict) -> ExtractedInfo:
    """Parse and validate the LLM's JSON response into ExtractedInfo."""

    def _edu_list(raw) -> list:
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            if isinstance(item, dict):
                result.append({
                    "degree": item.get("degree"),
                    "major": item.get("major"),
                    "school": item.get("school"),
                    "year": item.get("year"),
                })
        return result

    def _proj_list(raw) -> list:
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            if isinstance(item, dict):
                result.append({
                    "name": item.get("name"),
                    "role": item.get("role"),
                    "description": item.get("description"),
                    "duration_months": item.get("duration_months"),
                })
        return result

    def _str_list(raw) -> list:
        if not isinstance(raw, list):
            return []
        return [str(x) for x in raw if x]

    return ExtractedInfo(
        name=data.get("name"),
        phone=data.get("phone"),
        email=data.get("email"),
        address=data.get("address"),
        job_intent=data.get("job_intent"),
        expected_salary=data.get("expected_salary"),
        work_years=data.get("work_years"),
        education=_edu_list(data.get("education", [])),
        skills=_str_list(data.get("skills", [])),
        project_experience=_proj_list(data.get("project_experience", [])),
        languages=_str_list(data.get("languages", [])),
        certifications=_str_list(data.get("certifications", [])),
    )


def _regex_fallback(resume_text: str) -> ExtractedInfo:
    """Extract email and phone using regex when LLM is unavailable."""
    email = None
    phone = None

    # Extract email
    email_match = EMAIL_PATTERN.search(resume_text)
    if email_match:
        email = email_match.group(0)

    # Extract phone
    for pattern in PHONE_PATTERNS:
        phone_match = pattern.search(resume_text)
        if phone_match:
            phone = phone_match.group(0)
            break

    # Try to extract name (first non-empty line that looks like a name)
    name = None
    lines = [l.strip() for l in resume_text.split("\n") if l.strip()]
    if lines:
        first = lines[0]
        # If first line is short and doesn't contain obvious non-name text
        if len(first) < 50 and not re.search(r"resume|cv|curriculum|简历|个人", first, re.IGNORECASE):
            name = first

    logger.info(f"Regex fallback: email={email}, phone={phone}, name={name}")
    return ExtractedInfo(name=name, email=email, phone=phone)
