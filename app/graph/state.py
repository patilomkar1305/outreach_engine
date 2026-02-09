"""
app/graph/state.py
──────────────────
Enhanced State TypedDict with LLM action tracking for full visibility
into what the AI is doing at every stage.

Design rules:
  1. Fields are APPEND-only where possible (drafts, execution_results, llm_actions).
  2. "raw_*" fields are ephemeral – cleared by persona_agent after use.
  3. Nothing here is written to disk; the persistence node pulls what
     it needs, runs it through the sanitiser, then persists.
  4. Every LLM call is logged to llm_actions for frontend visibility.
  5. Stage timing is tracked for performance monitoring.

Field-by-field lifecycle
─────────────────────────
  raw_input            ingestion  →  persona  (deleted after persona)
  raw_profile_text     ingestion  →  persona  (deleted after persona)
  target_identifier    ingestion  →  persistence  (used for hashing only)
  target_hash          ingestion  →  persistence
  company / role / industry / links
                       ingestion  →  persistence
  tone                 persona    →  draft_agents
  similar_personas     persona    →  draft_agents  (context only)
  drafts               draft_agents → scoring → approval → execution → persistence
  scores               scoring    →  approval
  approved_channels    approval   →  execution
  execution_results    execution  →  persistence
  llm_actions          all nodes  →  API response (for frontend visibility)
  stages               all nodes  →  API response (for timing visibility)
  error                any node   →  persistence
"""

from __future__ import annotations
from typing import Any, TypedDict
from datetime import datetime
import uuid


class LLMAction(TypedDict):
    """Tracks every LLM call for frontend visibility."""
    id: str                     # unique action ID
    timestamp: str              # ISO format
    stage: str                  # "ingestion" | "persona" | "drafting" | "scoring" | etc.
    agent: str                  # specific agent name
    action: str                 # human-readable action description
    model: str                  # model used (e.g., "mistral")
    prompt_preview: str         # first 200 chars of prompt
    response_preview: str       # first 200 chars of response
    tokens_used: int | None     # if available
    duration_ms: int            # how long the call took
    status: str                 # "success" | "error"
    error_message: str | None   # if status is "error"


class Draft(TypedDict):
    """Enhanced draft with version tracking for regeneration."""
    id: str                     # unique draft ID
    channel: str                # "email" | "sms" | "linkedin" | "instagram" | "whatsapp"
    subject: str | None         # only for email
    body: str
    score: float | None         # filled by scoring agent (0-10)
    score_rationale: str | None # explanation of the score
    approved: bool              # filled by approval node
    sent: bool                  # filled by execution node
    version: int                # starts at 1, increments on regen
    regenerate_count: int       # how many times regenerated
    created_at: str             # ISO timestamp
    llm_action_id: str | None   # links to the LLM action that created it


class PersonaProfile(TypedDict):
    """Structured persona extracted from target profile."""
    name: str
    company: str
    role: str
    industry: str
    seniority: str              # "C-level" | "VP" | "Director" | "Manager" | "IC"
    communication_style: str    # "formal" | "casual" | "technical" | "friendly"
    key_interests: list[str]    # topics they care about
    pain_points: list[str]      # likely pain points to address
    decision_factors: list[str] # what influences their decisions
    recommended_approach: str   # AI recommendation for outreach approach
    confidence_score: float     # 0-1 confidence in the persona analysis


class StageInfo(TypedDict):
    """Tracks stage execution for timing visibility."""
    name: str
    started_at: str
    completed_at: str | None
    duration_ms: int | None
    status: str                 # "pending" | "running" | "completed" | "error"


class OutreachState(TypedDict, total=False):
    # ── ephemeral (ingestion → persona, then cleared) ─────────────────
    raw_input: str              # whatever the user pasted in
    raw_profile_text: str       # fetched / extracted text

    # ── stable identifiers (ingestion → persistence) ───────────────────
    target_identifier: str      # original input (URL / email) – NOT stored in DB
    target_hash: str            # SHA-256 of target_identifier

    # ── public business info ────────────────────────────────────────────
    company: str
    role: str
    industry: str
    links: dict[str, str]       # {"linkedin": url, ...}

    # ── persona / tone (persona → drafts) ────────────────────────────────
    tone: dict[str, Any]        # structured tone dict from persona agent
    persona: PersonaProfile     # detailed persona profile
    similar_personas: list[dict[str, Any]]  # from vector DB

    # ── drafts (parallel agents → scoring → approval → execution) ───────
    drafts: list[Draft]

    # ── approval (human-in-the-loop) ─────────────────────────────────────
    approved_channels: list[str]  # channels the user approved
    pending_approval: list[str]   # channels awaiting approval

    # ── execution results ────────────────────────────────────────────────
    execution_results: list[dict[str, Any]]

    # ── LLM action tracking (for frontend visibility) ────────────────────
    llm_actions: list[LLMAction]  # all LLM calls made during this run
    
    # ── Stage tracking (for timing visibility) ───────────────────────────
    stages: list[StageInfo]       # timing info for each stage

    # ── run metadata ─────────────────────────────────────────────────────
    run_id: str
    session_id: str             # for session persistence
    status: str                 # mirrors OutreachRun.status
    error: str | None
    created_at: str             # ISO timestamp
    updated_at: str             # ISO timestamp


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions for state manipulation
# ═══════════════════════════════════════════════════════════════════════════

def create_llm_action(
    stage: str,
    agent: str,
    action: str,
    model: str,
    prompt: str,
    response: str,
    duration_ms: int,
    status: str = "success",
    error_message: str | None = None,
    tokens_used: int | None = None,
) -> LLMAction:
    """Create a new LLM action record."""
    return LLMAction(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat() + "Z",
        stage=stage,
        agent=agent,
        action=action,
        model=model,
        prompt_preview=prompt[:200] + "..." if len(prompt) > 200 else prompt,
        response_preview=response[:200] + "..." if len(response) > 200 else response,
        tokens_used=tokens_used,
        duration_ms=duration_ms,
        status=status,
        error_message=error_message,
    )


def create_draft(
    channel: str,
    body: str,
    subject: str | None = None,
    llm_action_id: str | None = None,
) -> Draft:
    """Create a new draft record."""
    return Draft(
        id=str(uuid.uuid4()),
        channel=channel,
        subject=subject,
        body=body,
        score=None,
        score_rationale=None,
        approved=False,
        sent=False,
        version=1,
        regenerate_count=0,
        created_at=datetime.utcnow().isoformat() + "Z",
        llm_action_id=llm_action_id,
    )


def create_initial_state(
    run_id: str,
    session_id: str,
    raw_input: str,
) -> OutreachState:
    """Create initial state for a new outreach run."""
    now = datetime.utcnow().isoformat() + "Z"
    return OutreachState(
        run_id=run_id,
        session_id=session_id,
        raw_input=raw_input,
        drafts=[],
        llm_actions=[],
        stages=[],
        approved_channels=[],
        pending_approval=[],
        execution_results=[],
        status="pending",
        error=None,
        created_at=now,
        updated_at=now,
    )


def add_llm_action(state: OutreachState, action: LLMAction) -> OutreachState:
    """Add an LLM action to the state (immutable update)."""
    actions = list(state.get("llm_actions", []))
    actions.append(action)
    return {**state, "llm_actions": actions, "updated_at": datetime.utcnow().isoformat() + "Z"}


def start_stage(state: OutreachState, stage_name: str) -> OutreachState:
    """Mark a stage as started."""
    stages = list(state.get("stages", []))
    stages.append(StageInfo(
        name=stage_name,
        started_at=datetime.utcnow().isoformat() + "Z",
        completed_at=None,
        duration_ms=None,
        status="running",
    ))
    return {**state, "stages": stages, "updated_at": datetime.utcnow().isoformat() + "Z"}


def complete_stage(state: OutreachState, stage_name: str, status: str = "completed") -> OutreachState:
    """Mark a stage as completed with duration."""
    stages = list(state.get("stages", []))
    now = datetime.utcnow()
    for i, stage in enumerate(stages):
        if stage["name"] == stage_name and stage["status"] == "running":
            started = datetime.fromisoformat(stage["started_at"].rstrip("Z"))
            duration = int((now - started).total_seconds() * 1000)
            stages[i] = StageInfo(
                name=stage_name,
                started_at=stage["started_at"],
                completed_at=now.isoformat() + "Z",
                duration_ms=duration,
                status=status,
            )
            break
    return {**state, "stages": stages, "updated_at": now.isoformat() + "Z"}
