"""
app/agents/draft_agents.py
──────────────────────────
STAGE 3 – Parallel Draft Generation

Four independent node functions, one per channel.  LangGraph runs them
in parallel (see workflow.py).  Each one:
  1. Reads the tone profile + context from state.
  2. Builds a channel-specific prompt.
  3. Calls the local Ollama LLM.
  4. Returns a single Draft dict that gets merged into state["drafts"].

Each function is thin and self-contained – easy to swap the LLM or
add/remove channels later.
"""

from __future__ import annotations
import json
import logging
import re
import time
import uuid
from typing import Any
from datetime import datetime

from langchain_ollama import OllamaLLM

from app.config import settings
from app.graph.state import OutreachState, Draft, create_llm_action

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared LLM instance  (one per process – Ollama handles concurrency)
# ---------------------------------------------------------------------------
_llm: OllamaLLM | None = None


def _get_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=settings.ollama.model,
            base_url=settings.ollama.base_url,
            temperature=0.7,        # higher than persona – we want creative here
            num_predict=512,
        )
    return _llm


# ---------------------------------------------------------------------------
# Channel-specific prompt templates
# ─────────────────────────────────
# Each template receives:
#   {tone_summary}      – JSON-ified tone dict
#   {company}           – target's company
#   {role}              – target's role
#   {interests}         – comma-separated interests
#   {recent_activity}   – 1-2 sentence summary
#   {similar_examples}  – drafts from similar past personas (if any)
# ---------------------------------------------------------------------------

_EMAIL_PROMPT = """You are a world-class cold-outreach copywriter.
Write a cold EMAIL to a professional at {company} who works as a {role}.

─── TONE PROFILE (match this exactly) ───
{tone_summary}

─── CONTEXT ───
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples for reference:
{similar_examples}

─── REQUIREMENTS ───
• Subject line: compelling, personalised, under 60 chars.
• Body: 3-5 short paragraphs. Natural, human, NOT corporate.
• Mention their role / company / an interest naturally (no copy-paste feel).
• End with ONE clear CTA (reply, book a call, check a link).
• Match the tone profile above precisely.

─── OUTPUT FORMAT ───
Return ONLY a JSON object (no markdown, no explanation):
{{
  "subject": "<subject line>",
  "body": "<full email body with \\n for newlines>"
}}
"""

_SMS_PROMPT = """You are a concise, friendly SMS copywriter.
Write a cold SMS to a professional at {company} who works as a {role}.

─── TONE PROFILE ───
{tone_summary}

─── CONTEXT ───
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples:
{similar_examples}

─── REQUIREMENTS ───
• Max 160 characters (single SMS segment) if possible; 320 if needed.
• Casual but professional. One sentence + one CTA.
• Personalise with their role or company.
• Match the tone.

─── OUTPUT FORMAT ───
Return ONLY a JSON object:
{{
  "body": "<SMS text>"
}}
"""

_LINKEDIN_PROMPT = """You are a LinkedIn DM expert.
Write a cold LinkedIn DM to a {role} at {company}.

─── TONE PROFILE ───
{tone_summary}

─── CONTEXT ───
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples:
{similar_examples}

─── REQUIREMENTS ───
• 2-3 short paragraphs. Warm, professional, not salesy.
• Reference something specific about them (role, company, interest).
• End with a soft CTA (open a conversation, not a hard ask).
• Sound like a real person wrote it in 2 minutes.

─── OUTPUT FORMAT ───
Return ONLY a JSON object:
{{
  "body": "<LinkedIn DM text>"
}}
"""

_INSTAGRAM_PROMPT = """You are a casual, engaging Instagram DM writer.
Write a cold Instagram DM to a {role} at {company}.

─── TONE PROFILE ───
{tone_summary}

─── CONTEXT ───
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples:
{similar_examples}

─── REQUIREMENTS ───
• 1-2 short, punchy sentences. Very casual.
• Reference something real about them.
• End with an easy CTA (reply, check something out).
• Use natural language – maybe an emoji or two if the tone allows.

─── OUTPUT FORMAT ───
Return ONLY a JSON object:
{{
  "body": "<Instagram DM text>"
}}
"""

_WHATSAPP_PROMPT = """You are a friendly, concise WhatsApp message writer.
Write a cold WhatsApp message to a {role} at {company}.

─── TONE PROFILE ───
{tone_summary}

─── CONTEXT ───
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples:
{similar_examples}

─── REQUIREMENTS ───
• 2-3 short sentences max. Conversational and warm.
• Personalise with their role, company, or an interest.
• End with a soft CTA (reply, quick call, coffee chat).
• Match the tone – can use emojis if appropriate.
• Sound like a real WhatsApp message, not a formal letter.

─── OUTPUT FORMAT ───
Return ONLY a JSON object:
{{
  "body": "<WhatsApp message text>"
}}
"""

CHANNEL_PROMPTS: dict[str, str] = {
    "email":     _EMAIL_PROMPT,
    "sms":       _SMS_PROMPT,
    "linkedin": _LINKEDIN_PROMPT,
    "instagram": _INSTAGRAM_PROMPT,
    "whatsapp":  _WHATSAPP_PROMPT,
}


# ---------------------------------------------------------------------------
# Shared draft-generation logic
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned)
    cleaned = cleaned.strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No JSON found")
    depth, end = 0, start
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":   depth += 1
        elif ch == "}": depth -= 1
        if depth == 0:  end = i + 1; break
    return json.loads(cleaned[start:end])


def _generate_draft(channel: str, state: OutreachState) -> tuple[Draft, dict]:
    """Core logic shared by all channel nodes. Returns (draft, llm_action)."""
    tone = state.get("tone", {})
    company  = state.get("company", "their company")
    role     = state.get("role", "a professional")
    interests = ", ".join(tone.get("interests", []) or ["general topics"])
    recent   = tone.get("recent_activity_summary", "")

    # Pull drafts from similar past personas as examples
    similar_examples = ""
    for sp in (state.get("similar_personas") or []):
        summary = sp.get("tone_summary", "")
        if summary:
            similar_examples += f"  - {summary[:200]}\n"
    if not similar_examples:
        similar_examples = "  (none available)"

    prompt = CHANNEL_PROMPTS[channel].format(
        tone_summary=json.dumps(tone, indent=2),
        company=company,
        role=role,
        interests=interests,
        recent_activity=recent,
        similar_examples=similar_examples,
    )

    llm = _get_llm()
    logger.info("[%s] Calling Ollama …", channel.upper())
    start_time = time.time()
    raw_output = llm.invoke(prompt)
    duration_ms = int((time.time() - start_time) * 1000)
    logger.debug("[%s] Raw output:\n%s", channel.upper(), raw_output)

    parse_status = "success"
    parse_error = None
    try:
        parsed = _extract_json(raw_output)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("[%s] JSON parse failed: %s", channel.upper(), exc)
        parse_status = "error"
        parse_error = str(exc)
        parsed = {"body": raw_output.strip()[:1000]}

    # Create LLM action record
    action_id = str(uuid.uuid4())
    llm_action = create_llm_action(
        stage="drafting",
        agent=f"draft_{channel}_agent",
        action=f"Generating {channel.upper()} message draft",
        model=settings.ollama.model,
        prompt=prompt,
        response=raw_output,
        duration_ms=duration_ms,
        status=parse_status,
        error_message=parse_error,
    )

    # Create enhanced draft with tracking fields
    draft: Draft = {
        "id": str(uuid.uuid4()),
        "channel":  channel,
        "subject":  parsed.get("subject"),         # only email has this
        "body":     parsed.get("body", ""),
        "score":    None,
        "score_rationale": None,
        "approved": False,
        "sent":     False,
        "version": 1,
        "regenerate_count": 0,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "llm_action_id": llm_action["id"],
    }
    logger.info("[%s] Draft generated (%d chars)", channel.upper(), len(draft["body"]))
    return draft, llm_action


# ---------------------------------------------------------------------------
# Individual node functions  –  LangGraph calls each of these
# ---------------------------------------------------------------------------
# They all do the same thing but are separate so LangGraph can fan them out.

def draft_email_node(state: OutreachState) -> OutreachState:
    draft, llm_action = _generate_draft("email", state)
    return {"drafts": [draft], "llm_actions": [llm_action]}


def draft_sms_node(state: OutreachState) -> OutreachState:
    draft, llm_action = _generate_draft("sms", state)
    return {"drafts": [draft], "llm_actions": [llm_action]}


def draft_linkedin_node(state: OutreachState) -> OutreachState:
    draft, llm_action = _generate_draft("linkedin", state)
    return {"drafts": [draft], "llm_actions": [llm_action]}


def draft_instagram_node(state: OutreachState) -> OutreachState:
    draft, llm_action = _generate_draft("instagram", state)
    return {"drafts": [draft], "llm_actions": [llm_action]}


def draft_whatsapp_node(state: OutreachState) -> OutreachState:
    draft, llm_action = _generate_draft("whatsapp", state)
    return {"drafts": [draft], "llm_actions": [llm_action]}
