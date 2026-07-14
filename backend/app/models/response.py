"""Uniform API response models."""
from typing import Any, Optional, Dict
from pydantic import BaseModel
from datetime import datetime


class APIResponse(BaseModel):
    """Uniform envelope for all API responses."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class HealthData(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"


class UploadData(BaseModel):
    resume_id: str
    filename: str
    page_count: int
    raw_text_length: int
    cleaned_text: str


class Education(BaseModel):
    degree: Optional[str] = None
    major: Optional[str] = None
    school: Optional[str] = None
    year: Optional[int] = None


class ProjectExperience(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    duration_months: Optional[int] = None


class ExtractedInfo(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    job_intent: Optional[str] = None
    expected_salary: Optional[str] = None
    work_years: Optional[int] = None
    education: list = []
    skills: list = []
    project_experience: list = []
    languages: list = []
    certifications: list = []


class ExtractData(BaseModel):
    resume_id: str
    extracted: ExtractedInfo
    raw_llm_response: Optional[str] = None


class KeywordItem(BaseModel):
    term: str
    weight: float
    category: str


class JDKeywordsData(BaseModel):
    keywords: list


class ScoreBreakdown(BaseModel):
    skill_match: Optional[Dict[str, Any]] = None
    experience_match: Optional[Dict[str, Any]] = None
    education_match: Optional[Dict[str, Any]] = None
    keyword_overlap: Optional[Dict[str, Any]] = None


class ScoreData(BaseModel):
    resume_id: str
    overall_score: float
    breakdown: ScoreBreakdown
    matched_keywords: list = []
    missing_keywords: list = []
    ai_analysis: Optional[str] = None


class AnalyzeData(BaseModel):
    resume_id: str
    filename: str
    page_count: int
    cleaned_text: str
    extracted: Optional[ExtractedInfo] = None
    score: Optional[ScoreData] = None
