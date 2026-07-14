"""Pydantic request models for API endpoints."""
from typing import Optional
from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    resume_id: str = Field(..., description="Resume identifier from upload")
    resume_text: str = Field(..., min_length=10, description="Cleaned resume text")


class JDKeywordsRequest(BaseModel):
    jd_text: str = Field(..., min_length=10, description="Job description text")


class ScoreRequest(BaseModel):
    resume_id: str = Field(..., description="Resume identifier")
    resume_text: str = Field(..., min_length=10, description="Cleaned resume text")
    jd_text: str = Field(..., min_length=10, description="Job description text")
    mode: str = Field(default="basic", pattern="^(basic|ai)$", description="Scoring mode: basic or ai")
