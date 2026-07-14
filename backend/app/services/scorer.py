"""Resume scoring and job matching service.

Two modes:
- basic: keyword overlap + rule-based weighted scoring (fast, no LLM)
- ai: LLM-based precise comparison (slower, higher quality)
"""
import re
import math
from typing import List, Tuple, Dict, Any, Optional
from app.services.llm_service import llm_service
from app.models.response import ScoreData, ScoreBreakdown
from app.utils.helpers import logger

# ---------------------------------------------------------------------------
# Common English + Chinese stopwords for JD keyword extraction
# ---------------------------------------------------------------------------
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "and",
    "or", "not", "no", "but", "if", "then", "else", "when", "where",
    "we", "you", "our", "your", "their", "its", "this", "that", "these",
    "those", "about", "each", "all", "any", "both", "such", "only",
    "other", "more", "some", "very", "just", "also", "now", "new",
    "work", "team", "role", "job", "position", "candidate", "looking",
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们",
}

# ---------------------------------------------------------------------------
# Skill/tech keyword patterns for better matching
# ---------------------------------------------------------------------------
TECH_PATTERNS = re.compile(
    r"\b(?:"
    r"Python|Java|JavaScript|TypeScript|Go|Rust|C\+\+|C#|Ruby|PHP|Swift|Kotlin|"
    r"React|Vue|Angular|Node\.js|Django|Flask|FastAPI|Spring|Express|"
    r"Docker|Kubernetes|AWS|Azure|GCP|Terraform|Ansible|Jenkins|"
    r"SQL|MySQL|PostgreSQL|MongoDB|Redis|Elasticsearch|Kafka|RabbitMQ|"
    r"TensorFlow|PyTorch|ML|AI|NLP|Computer Vision|Deep Learning|"
    r"Git|CI/CD|DevOps|Agile|Scrum|Linux|Unix|REST|GraphQL|gRPC|"
    r"Microservices|Serverless|Cloud|Big Data|Hadoop|Spark"
    r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------
WEIGHTS = {
    "skill_match": 0.40,
    "experience_match": 0.30,
    "education_match": 0.15,
    "keyword_overlap": 0.15,
}


# ---------------------------------------------------------------------------
# Prompt for AI-mode scoring
# ---------------------------------------------------------------------------
SCORING_SYSTEM_PROMPT = """You are a professional recruitment consultant and resume evaluator. Your task is to compare a candidate's resume against a job description and provide a detailed match analysis.

You MUST return ONLY a valid JSON object. No markdown, no explanation, no code fences.

The JSON object must follow this schema:
{
  "overall_score": <number 0-100>,
  "breakdown": {
    "skill_match": {"score": <number 0-100>, "details": "<explanation>"},
    "experience_match": {"score": <number 0-100>, "details": "<explanation>"},
    "education_match": {"score": <number 0-100>, "details": "<explanation>"},
    "keyword_overlap": {"score": <number 0-100>, "matched": ["<skill>", ...], "missing": ["<skill>", ...]}
  },
  "matched_keywords": ["<keyword>", ...],
  "missing_keywords": ["<keyword>", ...],
  "ai_analysis": "<2-3 sentence summary of the candidate's fit>"
}

Scoring guidelines:
- 90-100: Excellent match, ideal candidate
- 75-89: Strong match, most requirements met
- 60-74: Moderate match, some gaps
- 40-59: Weak match, significant gaps
- Below 40: Poor match

Be objective and precise. Consider both hard skills and soft requirements mentioned in the JD."""

SCORING_USER_PROMPT = """Please evaluate how well this candidate's resume matches the job description.

=== JOB DESCRIPTION ===
{jd_text}

=== RESUME ===
{resume_text}

Provide a detailed match analysis as a JSON object."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_jd_keywords(jd_text: str) -> List[Dict[str, Any]]:
    """Extract weighted keywords from job description text.

    Uses TF-based weighting with tech-pattern detection.

    Args:
        jd_text: Job description text.

    Returns:
        List of keyword dicts: {"term": str, "weight": float, "category": str}
    """
    # Tokenize
    words = re.findall(r"[a-zA-Z#+\-.]{2,}|\w{2,}", jd_text.lower())

    # Filter stopwords and short tokens
    filtered = [w for w in words if w not in STOPWORDS and len(w) >= 2]

    # Count frequencies
    freq: Dict[str, int] = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1

    max_freq = max(freq.values()) if freq else 1

    # Also find multi-word tech terms
    tech_terms = set()
    for match in TECH_PATTERNS.finditer(jd_text):
        tech_terms.add(match.group(0).lower())

    keywords = []
    seen = set()

    # Add tech terms first (higher weight)
    for term in tech_terms:
        if term not in seen:
            seen.add(term)
            keywords.append({
                "term": term,
                "weight": 0.9,
                "category": "skill",
            })

    # Add frequency-based keywords
    for term, count in freq.items():
        if term not in seen:
            seen.add(term)
            weight = round(count / max_freq, 2)
            # Categorize
            if _is_skill_term(term):
                cat = "skill"
            elif any(w in term for w in ["year", "experience", "经验"]):
                cat = "experience"
            elif any(w in term for w in ["degree", "bachelor", "master", "phd", "学历", "本科", "硕士"]):
                cat = "education"
            else:
                cat = "general"
            keywords.append({"term": term, "weight": weight, "category": cat})

    # Sort by weight descending
    keywords.sort(key=lambda x: x["weight"], reverse=True)
    return keywords[:30]  # Top 30


def score_basic(resume_text: str, jd_text: str) -> ScoreData:
    """Basic keyword-overlap + rule-based scoring.

    No LLM call — fast and always available.

    Args:
        resume_text: Cleaned resume text.
        jd_text: Job description text.

    Returns:
        ScoreData with overall score and breakdown.
    """
    jd_keywords = extract_jd_keywords(jd_text)
    resume_lower = resume_text.lower()
    jd_lower = jd_text.lower()

    # ---- Skill match ----
    skill_keywords = [k for k in jd_keywords if k["category"] == "skill"]
    matched_skills = []
    missing_skills = []
    for kw in skill_keywords:
        if kw["term"] in resume_lower:
            matched_skills.append(kw["term"])
        else:
            missing_skills.append(kw["term"])

    if skill_keywords:
        skill_score = round((len(matched_skills) / len(skill_keywords)) * 100, 1)
    else:
        skill_score = 50.0

    # ---- Experience match ----
    exp_score = _match_work_years(resume_text, jd_text)
    exp_keywords = [k for k in jd_keywords if k["category"] == "experience"]
    if exp_keywords:
        exp_matched = [k["term"] for k in exp_keywords if k["term"] in resume_lower]
        exp_overlap = len(exp_matched) / len(exp_keywords) if exp_keywords else 0
        exp_score = round(exp_score * 0.6 + exp_overlap * 100 * 0.4, 1)
    else:
        exp_score = round(exp_score, 1)

    # ---- Education match ----
    edu_score = _match_education(resume_text, jd_text)

    # ---- Keyword overlap ----
    all_kw = [k for k in jd_keywords if k["category"] != "skill"]
    matched_all = [k["term"] for k in all_kw if k["term"] in resume_lower]
    missing_all = [k["term"] for k in all_kw if k["term"] not in resume_lower]

    if all_kw:
        kw_score = round((len(matched_all) / len(all_kw)) * 100, 1)
    else:
        kw_score = 50.0

    # ---- Overall weighted score ----
    overall = round(
        WEIGHTS["skill_match"] * skill_score
        + WEIGHTS["experience_match"] * exp_score
        + WEIGHTS["education_match"] * edu_score
        + WEIGHTS["keyword_overlap"] * kw_score,
        1,
    )

    # Build breakdown
    breakdown = ScoreBreakdown(
        skill_match={
            "score": skill_score,
            "details": f"Matched {len(matched_skills)}/{len(skill_keywords)} required skills" if skill_keywords else "No skill keywords found",
        },
        experience_match={
            "score": exp_score,
            "details": f"Experience match based on work years and keywords",
        },
        education_match={
            "score": edu_score,
            "details": "Education level match",
        },
        keyword_overlap={
            "score": kw_score,
            "matched": matched_all[:15],
            "missing": missing_all[:15],
        },
    )

    return ScoreData(
        resume_id="",  # Will be set by caller
        overall_score=overall,
        breakdown=breakdown,
        matched_keywords=list(set(matched_skills + matched_all))[:20],
        missing_keywords=list(set(missing_skills + missing_all))[:20],
    )


async def score_ai(resume_text: str, jd_text: str) -> ScoreData:
    """AI-powered precise scoring using LLM.

    Falls back to basic scoring if LLM fails.

    Args:
        resume_text: Cleaned resume text.
        jd_text: Job description text.

    Returns:
        ScoreData with AI analysis.
    """
    try:
        prompt = SCORING_USER_PROMPT.format(
            jd_text=jd_text[:4000],
            resume_text=resume_text[:4000],
        )
        result = await llm_service.chat_json(
            prompt=prompt,
            system_prompt=SCORING_SYSTEM_PROMPT,
            temperature=0.4,
        )
        logger.info("AI scoring succeeded")

        breakdown = ScoreBreakdown(
            skill_match=result.get("breakdown", {}).get("skill_match"),
            experience_match=result.get("breakdown", {}).get("experience_match"),
            education_match=result.get("breakdown", {}).get("education_match"),
            keyword_overlap=result.get("breakdown", {}).get("keyword_overlap"),
        )

        return ScoreData(
            resume_id="",
            overall_score=float(result.get("overall_score", 50)),
            breakdown=breakdown,
            matched_keywords=result.get("matched_keywords", []),
            missing_keywords=result.get("missing_keywords", []),
            ai_analysis=result.get("ai_analysis"),
        )

    except Exception as e:
        logger.warning(f"AI scoring failed, falling back to basic: {e}")
        result = score_basic(resume_text, jd_text)
        result.ai_analysis = f"(AI scoring unavailable — showing basic match. Error: {e})"
        return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _is_skill_term(term: str) -> bool:
    """Check if a term looks like a skill/technology."""
    skill_indicators = [
        "python", "java", "javascript", "typescript", "go", "rust", "c++",
        "react", "vue", "angular", "node", "django", "flask", "fastapi",
        "docker", "kubernetes", "aws", "azure", "gcp", "sql", "mysql",
        "postgresql", "mongodb", "redis", "kafka", "tensorflow", "pytorch",
        "git", "linux", "rest", "graphql", "microservices", "serverless",
        "devops", "ci/cd", "agile", "scrum",
    ]
    return term.lower() in skill_indicators


def _match_work_years(resume_text: str, jd_text: str) -> float:
    """Estimate work-years match between resume and JD."""
    # Extract years from JD
    jd_years_match = re.search(r"(\d+)[\+]?\s*(?:years?|yrs?|年)", jd_text, re.IGNORECASE)
    jd_years = int(jd_years_match.group(1)) if jd_years_match else None

    # Extract years from resume
    resume_years_match = re.findall(r"(\d+)[\+]?\s*(?:years?|yrs?|年)", resume_text, re.IGNORECASE)
    if resume_years_match:
        resume_years = max(int(y) for y in resume_years_match)
    else:
        resume_years = None

    if jd_years is None:
        return 70.0  # No explicit requirement — neutral

    if resume_years is None:
        return 40.0  # Can't determine from resume

    if resume_years >= jd_years:
        return min(100.0, 80.0 + (resume_years - jd_years) * 5)
    else:
        gap = jd_years - resume_years
        return max(10.0, 80.0 - gap * 20)


def _match_education(resume_text: str, jd_text: str) -> float:
    """Estimate education-level match."""
    edu_levels = {
        "phd": 5, "博士": 5, "doctorate": 5,
        "master": 4, "硕士": 4, "ms": 4, "ma": 4, "mba": 4,
        "bachelor": 3, "本科": 3, "bs": 3, "ba": 3, "学士": 3,
        "associate": 2, "大专": 2, "college": 2,
        "high school": 1, "高中": 1,
    }

    jd_level = 0
    for term, level in edu_levels.items():
        if term in jd_text.lower():
            jd_level = max(jd_level, level)

    resume_level = 0
    for term, level in edu_levels.items():
        if term in resume_text.lower():
            resume_level = max(resume_level, level)

    if jd_level == 0:
        return 70.0  # No explicit requirement

    if resume_level >= jd_level:
        return min(100.0, 80.0 + (resume_level - jd_level) * 10)
    else:
        gap = jd_level - resume_level
        return max(10.0, 80.0 - gap * 25)
