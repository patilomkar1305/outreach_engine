"""
app/agents/approval_and_persistence.py
──────────────────────────────────────
Two nodes that don't call the LLM:

  1. approval_node   – Human-in-the-loop.  Uses langgraph.interrupt()
       to pause the graph and surface each draft + its score to the
       user via a pretty CLI prompt.  The user can:
           • approve   – channel goes into approved_channels
           • regen     – channel is flagged; the workflow re-runs that
                         single draft node (handled in workflow.py)
           • skip      – draft is dropped silently

  2. persistence_node – After execution, sanitises the state and writes:
           • TargetProfile + PersonaRecord + DraftRecord + OutreachRun → Postgres
           • tone summary → ChromaDB (for future similarity queries)
"""

from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from langgraph.types import interrupt

from app.graph.state   import OutreachState
from app.utils.sanitizer import sanitize_for_storage, compute_target_hash

logger = logging.getLogger(__name__)


# ===========================================================================
# 1. APPROVAL NODE
# ===========================================================================
# LangGraph interrupt() pauses execution and surfaces a value to the
# caller (main.py).  main.py reads it, prompts the user, and resumes
# with the user's choices.  This node therefore has TWO code-paths:
#
#   A) First entry  – builds the interrupt payload.
#   B) Resumed      – receives the human's choices, writes approved_channels.
#
# We distinguish them by checking whether state already has
# "approved_channels" set (set only on resume).
# ===========================================================================

def _format_drafts_for_display(drafts: list[dict]) -> str:
    """Pretty string for the CLI prompt."""
    lines: list[str] = []
    for i, d in enumerate(drafts, 1):
        score_str = f"{d.get('score', 'N/A')}/10" if d.get("score") is not None else "N/A"
        lines.append(f"\n{'─' * 55}")
        lines.append(f"  [{i}] CHANNEL : {d['channel'].upper()}   |  SCORE : {score_str}")
        if d.get("subject"):
            lines.append(f"      Subject : {d['subject']}")
        lines.append(f"      Body    :\n{d['body']}")
    lines.append(f"\n{'─' * 55}")
    return "\n".join(lines)


def approval_node(state: OutreachState) -> OutreachState:
    """
    Interrupt-based approval.

    On FIRST call: raises an interrupt with the drafts so the outer
    loop in main.py can display them and collect human input.

    On RESUME (after the human responds): the resumed value is a dict
    like  {"approved": ["email", "linkedin"], "regen": ["sms"]}
    and we write it into state.
    """
    # ── Check if we are being resumed with human input ──────────────
    # LangGraph passes the resume value as state["__resume__"] when
    # using the Command pattern.  We also accept it directly.
    resume_value = state.get("__resume__")          # set by main.py on resume

    if resume_value and isinstance(resume_value, dict):
        # We have the human's choices – apply them
        approved  = resume_value.get("approved", [])
        regen     = resume_value.get("regen",    [])

        # Mark approved on each draft
        updated_drafts = []
        for d in state.get("drafts", []):
            if d["channel"] in approved:
                d = {**d, "approved": True}
            updated_drafts.append(d)

        logger.info("Approval: approved=%s  regen=%s", approved, regen)
        return {
            "drafts":            updated_drafts,
            "approved_channels": approved,
            "regen_channels":    regen,
            "status":            "approved",
        }

    # ── FIRST CALL – pause and surface drafts to the user ───────────
    drafts = state.get("drafts", [])
    display = _format_drafts_for_display(drafts)

    # interrupt() pauses the graph and returns the payload to the caller
    interrupt({
        "type":    "approval_required",
        "drafts":  drafts,
        "display": display,
        "instructions": (
            "For each draft, choose: approve | regen | skip\n"
            "Example input:  email=approve sms=regen linkedin=approve instagram=skip"
        ),
    })

    # If interrupt is not supported in the current runtime (e.g. sync invoke),
    # fall back to an inline CLI prompt:
    return _inline_cli_approval(state)


def _inline_cli_approval(state: OutreachState) -> OutreachState:
    """
    Fallback: blocking CLI prompt when interrupt() can't be used.
    """
    drafts = state.get("drafts", [])
    print(_format_drafts_for_display(drafts))
    print("\nFor each draft, choose:  approve | regen | skip")
    print("Example:  email=approve sms=regen linkedin=approve instagram=skip\n")

    raw = input(">>> ").strip()

    approved:  list[str] = []
    regen:     list[str] = []

    for token in raw.split():
        if "=" not in token:
            continue
        channel, choice = token.split("=", 1)
        channel = channel.strip().lower()
        choice  = choice.strip().lower()
        if choice == "approve":
            approved.append(channel)
        elif choice == "regen":
            regen.append(channel)
        # "skip" → do nothing

    updated_drafts = []
    for d in drafts:
        if d["channel"] in approved:
            d = {**d, "approved": True}
        updated_drafts.append(d)

    logger.info("CLI Approval: approved=%s  regen=%s", approved, regen)
    return {
        "drafts":            updated_drafts,
        "approved_channels": approved,
        "regen_channels":    regen,
        "status":            "approved",
    }


# ===========================================================================
# 2. PERSISTENCE NODE
# ===========================================================================

def persistence_node(state: OutreachState) -> OutreachState:
    """
    Writes sanitised data to Postgres AND ChromaDB.

    Runs synchronously by wrapping the async Postgres calls in
    asyncio.run() (safe because LangGraph node functions are sync by default).
    """
    logger.info("=== PERSISTENCE START ===")

    # ── Sanitise ─────────────────────────────────────────────────────
    safe = sanitize_for_storage(state)
    target_hash = state.get("target_hash", compute_target_hash("unknown"))

    # ── 1. ChromaDB – upsert persona tone for future similarity ──────
    tone = state.get("tone", {})
    tone_summary = (
        f"{tone.get('formality_level', '')} | "
        f"{tone.get('communication_style', '')} | "
        f"keywords: {', '.join(tone.get('tone_keywords', []))}"
    )
    try:
        from app.db.vector_store import upsert_persona
        upsert_persona(
            target_hash=target_hash,
            tone_summary=tone_summary,
            metadata={
                "industry": safe.get("industry", ""),
                "company":  safe.get("company", ""),
                "role":     safe.get("role", ""),
            },
        )
        logger.info("ChromaDB upsert OK.")
    except Exception as exc:
        logger.error("ChromaDB upsert failed: %s", exc, exc_info=True)

    # ── 2. Postgres – write profile + persona + drafts + run ─────────
    try:
        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - create a task in a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.submit(lambda: asyncio.run(_persist_to_postgres(target_hash, safe, state))).result()
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            asyncio.run(_persist_to_postgres(target_hash, safe, state))
        
        logger.info("Postgres persist OK.")
    except Exception as exc:
        logger.error("Postgres persist failed: %s", exc, exc_info=True)
        # Pipeline does NOT fail here – outreach already sent.

    return {"status": "persisted"}


# ---------------------------------------------------------------------------
# Async Postgres helpers
# ---------------------------------------------------------------------------

async def _persist_to_postgres(
    target_hash: str,
    safe: dict[str, Any],
    full_state: OutreachState,
) -> None:
    from app.db.engine  import get_session
    from app.db.models  import (
        TargetProfile, PersonaRecord, DraftRecord, OutreachRun,
    )

    async with get_session() as session:
        # ── TargetProfile  (upsert-style: check existence first) ──
        from sqlalchemy import select
        existing = await session.execute(
            select(TargetProfile).where(TargetProfile.target_hash == target_hash)
        )
        profile = existing.scalar_one_or_none()

        if profile is None:
            profile = TargetProfile(
                target_hash=target_hash,
                company=safe.get("company"),
                role=safe.get("role"),
                industry=safe.get("industry"),
                links=safe.get("links"),
            )
            session.add(profile)
            await session.flush()   # get the generated PK

        # ── PersonaRecord ─────────────────────────────────────────
        tone = full_state.get("tone", {})
        persona = PersonaRecord(
            target_id=profile.id,
            formality_level=tone.get("formality_level"),
            communication_style=tone.get("communication_style"),
            language_hints=tone.get("language_hints"),
            interests=tone.get("interests"),
            recent_activity=safe.get("recent_activity"),
            tone_json=tone,
        )
        session.add(persona)

        # ── OutreachRun ───────────────────────────────────────────
        run_id = uuid.uuid4()
        run = OutreachRun(
            id=run_id,
            target_id=profile.id,
            status=full_state.get("status", "executed"),
            completed_at=datetime.utcnow(),
        )
        session.add(run)

        # ── DraftRecords ──────────────────────────────────────────
        for d in safe.get("drafts", []):
            draft_record = DraftRecord(
                target_id=profile.id,
                run_id=run_id,
                channel=d.get("channel", "unknown"),
                subject=d.get("subject"),
                body=d.get("body", ""),
                score=d.get("score"),
                approved=d.get("approved", False),
                sent=d.get("sent", False),
            )
            session.add(draft_record)

        # session auto-commits on exit (see engine.py)
        logger.debug("Postgres: flushing %d objects", len(session.new))
