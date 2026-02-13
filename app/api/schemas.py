"""
app/api/schemas.py
──────────────────
Pydantic request/response models for the API.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ── Request schemas ────────────────────────────────────────────────────────

class CampaignStartRequest(BaseModel):
    """Request to start a new outreach campaign."""
    input_type: str = Field(..., description="'url', 'text', or 'file'")
    content: str = Field(..., description="URL, text, or file path")
    session_id: str | None = Field(None, description="Optional session ID to append to existing session")


class DraftActionRequest(BaseModel):
    """Request to approve/regen/skip a draft."""
    action: str = Field(..., description="'approve', 'regen', or 'skip'")


# ── Response schemas ───────────────────────────────────────────────────────

class LLMActionResponse(BaseModel):
    """Single LLM action for visibility panel."""
    id: str
    timestamp: str
    stage: str
    agent: str
    action: str
    model: str
    prompt_preview: str
    response_preview: str
    tokens_used: int | None = None
    duration_ms: int
    status: str
    error_message: str | None = None


class StageInfoResponse(BaseModel):
    """Stage timing information."""
    name: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    status: str


class DraftResponse(BaseModel):
    """Single draft channel response."""
    id: str | None = None
    channel: str
    subject: str | None = None
    body: str
    score: float | None = None
    score_rationale: str | None = None
    approved: bool = False
    sent: bool = False
    version: int = 1
    regenerate_count: int = 0
    created_at: str | None = None


class PersonaResponse(BaseModel):
    """Extracted persona profile."""
    name: str | None = None
    company: str | None = None
    role: str | None = None
    industry: str | None = None
    seniority: str | None = None
    communication_style: str | None = None
    formality_level: str | None = None
    tone_keywords: list[str] = []
    language_hints: str | None = None
    key_interests: list[str] = []
    pain_points: list[str] = []
    decision_factors: list[str] = []
    recommended_approach: str | None = None
    confidence_score: float | None = None


class StageUpdate(BaseModel):
    """Real-time stage progress update."""
    stage: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CampaignResponse(BaseModel):
    """Campaign status and results."""
    campaign_id: str
    session_id: str | None = None
    status: str
    current_stage: str
    target_company: str | None = None
    target_role: str | None = None
    drafts: list[DraftResponse] = []
    llm_actions: list[LLMActionResponse] = []
    stages: list[StageInfoResponse] = []
    persona: PersonaResponse | None = None
    error: str | None = None


# ── Session schemas ────────────────────────────────────────────────────────

class SessionSummary(BaseModel):
    """Summary of a session for the sidebar."""
    session_id: str
    name: str
    created_at: str
    updated_at: str
    campaign_count: int
    last_company: str | None = None
    last_role: str | None = None


class SessionDetail(BaseModel):
    """Full session details with all campaigns."""
    session_id: str
    name: str
    created_at: str
    updated_at: str
    campaigns: list[CampaignResponse] = []


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""
    name: str | None = Field(None, description="Optional session name")
