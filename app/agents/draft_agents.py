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
            temperature=0.65,        # balanced creativity with coherence
            num_predict=800,         # enough room for detailed messages
            top_p=0.9,               # nucleus sampling for diversity
            repeat_penalty=1.15,     # reduce repetition
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

_EMAIL_PROMPT = """You are a world-class cold-outreach copywriter who writes emails that feel like they were hand-crafted by a thoughtful human.
Write a cold EMAIL to {name}, a {role} at {company}.

─── TONE PROFILE (match this exactly) ───
{tone_summary}

─── CONTEXT ───
Target person: {name}
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples for reference:
{similar_examples}

─── REQUIREMENTS ───
• ALWAYS address them as "{first_name}" in the greeting – never use placeholders like [Name] or [First Name].
• Subject line: compelling, personalised, under 60 chars. Reference them, their company, or something specific about them.
• Body: 2-4 short paragraphs. Warm, genuine, conversational – NOT corporate or salesy.
• Open with something specific about them – a recent achievement, their role, an interest, or something you genuinely admire. Make it feel like you actually looked them up.
• Middle: briefly connect what you do to what they care about. Show value without being pushy.
• End with ONE soft, low-pressure CTA – a quick chat, a reply, or checking something out. No "I'd love to schedule a 30-minute demo" energy.
• Sound like a real person wrote this in 5 minutes because they were genuinely interested.
• NEVER use placeholders like [Your Name], [Name], or [Company]. Sign off naturally – use a warm closing like "Cheers" or "Best" without a sender name.
• Match the tone profile above precisely.
• Use 1-2 relevant emojis where they enhance the message (e.g. in the subject line or sign-off). Keep it professional — emojis should feel natural, not forced.

─── OUTPUT FORMAT ───
Return ONLY a JSON object (no markdown, no explanation):
{{
  "subject": "<subject line>",
  "body": "<full email body with \\n for newlines>"
}}
"""

_SMS_PROMPT = """You are a concise, friendly SMS copywriter who writes texts that feel personal, not automated.
Write a cold SMS to {name}, a {role} at {company}.

─── TONE PROFILE ───
{tone_summary}

─── CONTEXT ───
Target person: {name}
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples:
{similar_examples}

─── REQUIREMENTS ───
• ALWAYS use their first name "{first_name}" – never placeholders like [Name].
• Max 160 characters (single SMS segment) if possible; absolutely no more than 320.
• Casual but professional. Feel like a text from someone they'd want to reply to.
• Reference something specific – their company, role, a recent achievement, or an interest. Don't be generic.
• End with a soft, easy CTA – a reply, a quick call, checking something out.
• Match the tone profile. Sound like a real person texting, not a marketing blast.
• You may include 1 emoji if it fits naturally, but it's also fine to skip emojis entirely — SMS should feel short and human.

─── OUTPUT FORMAT ───
Return ONLY a JSON object:
{{
  "body": "<SMS text>"
}}
"""

_LINKEDIN_PROMPT = """You are a LinkedIn DM expert who writes thoughtful, engaging connection messages.
Write a cold LinkedIn DM to {name}, a {role} at {company}.

─── TONE PROFILE ───
{tone_summary}

─── CONTEXT ───
Target person: {name}
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples:
{similar_examples}

─── REQUIREMENTS ───
• ALWAYS address them as "{first_name}" in the greeting – never use placeholders.
• 3-4 paragraphs. Warm, professional, not salesy.
• Open with a specific, genuine compliment about their work, a recent post, a company milestone, or something you admire about their career trajectory. Show you actually looked at their profile.
• In the middle, briefly connect your work/interest to theirs. Share one concrete insight, observation, or question that demonstrates you understand their space. Make it a two-way conversation, not a pitch.
• End with a soft, specific CTA – suggest a topic to discuss, a coffee chat, or exchanging perspectives on something relevant. Make it easy to say yes.
• Sound like a real person who took 3-4 minutes to write a thoughtful message because they were genuinely interested.
• Include 1-2 tasteful emojis where they add warmth (e.g. 👋 in the greeting, or a subtle one at the end). Keep it professional-friendly.

─── OUTPUT FORMAT ───
Return ONLY a JSON object:
{{
  "body": "<LinkedIn DM text>"
}}
"""

_INSTAGRAM_PROMPT = """You are a casual, engaging Instagram DM writer who sounds like a real person, not a brand.
Write a cold Instagram DM to {name}, a {role} at {company}.

─── TONE PROFILE ───
{tone_summary}

─── CONTEXT ───
Target person: {name}
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples:
{similar_examples}

─── REQUIREMENTS ───
• ALWAYS use their first name "{first_name}" – never placeholders.
• 2-3 short, punchy sentences. Casual, warm, platform-native.
• Open with something specific about them – their content, work, an achievement, or a shared interest. Make it feel like you actually follow them.
• Keep it conversational and genuine – Instagram DMs should feel like a real person sliding in, not a cold pitch.
• End with an easy, low-pressure CTA – a reply, checking something out, or connecting further.
• Use 2-4 emojis naturally throughout the message — Instagram DMs should feel expressive and engaging 🔥✨. Place them where they add energy or punctuate a point.
• Sound like you wrote this in under a minute because you were genuinely interested.

─── OUTPUT FORMAT ───
Return ONLY a JSON object:
{{
  "body": "<Instagram DM text>"
}}
"""

_WHATSAPP_PROMPT = """You are a friendly, natural WhatsApp message writer who sounds like a real person reaching out genuinely.
Write a cold WhatsApp message to {name}, a {role} at {company}.

─── TONE PROFILE ───
{tone_summary}

─── CONTEXT ───
Target person: {name}
Interests: {interests}
Recent activity: {recent_activity}
Past similar examples:
{similar_examples}

─── REQUIREMENTS ───
• ALWAYS use their first name "{first_name}" – never placeholders.
• 2-3 short sentences max. Conversational, warm, like you're texting a new professional contact.
• Open with something specific – reference their role, company, a recent achievement, or a shared interest. Show you know who they are.
• Keep it personal and genuine – WhatsApp messages should feel like a real person reaching out, not a template.
• End with a soft CTA – a reply, quick call, or coffee chat. Keep it low-pressure.
• Use 2-3 emojis naturally — WhatsApp is a casual platform and emojis make messages feel warmer and more genuine 😊👋. Place them where they feel conversational.
• Sound like you took 30 seconds to write this because you were genuinely excited about connecting.

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

def _sanitize_json_newlines(s: str) -> str:
    """Replace literal newlines inside JSON string values with \\n."""
    result = []
    in_string = False
    escape = False
    for ch in s:
        if escape:
            result.append(ch)
            escape = False
            continue
        if ch == '\\' and in_string:
            result.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch == '\n':
            result.append('\\n')
            continue
        if in_string and ch == '\r':
            continue
        result.append(ch)
    return ''.join(result)


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
    json_str = cleaned[start:end]

    # First try parsing as-is
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Fallback: fix literal newlines inside string values
    fixed = _sanitize_json_newlines(json_str)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"Could not parse JSON from LLM output: {json_str[:200]}")


def _extract_draft_fallback(raw: str, channel: str) -> dict[str, Any]:
    """Fallback extraction when JSON parsing fails.
    
    Handles common LLM failures like unquoted body values, preamble text,
    or slightly malformed JSON.
    """
    result: dict[str, Any] = {}

    # Try to extract subject (email only) from "subject": "..." pattern
    if channel == "email":
        subject_match = re.search(r'"subject"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        if subject_match:
            result["subject"] = subject_match.group(1)

    # Try to extract body from "body":\s* pattern
    body_match = re.search(r'"body"\s*:\s*"?(.*)', raw, re.DOTALL)
    if body_match:
        body = body_match.group(1)
        # Remove trailing JSON artifacts
        body = re.sub(r'\}\s*$', '', body)
        body = body.strip().rstrip('"').strip()
        if body:
            result["body"] = body
            return result

    # Final fallback: strip common LLM preamble and JSON wrapper
    cleaned = re.sub(
        r'^(?:Here is|Here\'s|Below is|I\'ve written).*?:\s*\n+',
        '', raw.strip(), flags=re.IGNORECASE
    )
    # Remove JSON wrapper if present
    cleaned = re.sub(r'^\{[^}]*?"(?:body|subject)"\s*:\s*', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'\}\s*$', '', cleaned).strip()
    if cleaned:
        result["body"] = cleaned[:2000]

    return result


def _generate_draft(channel: str, state: OutreachState) -> tuple[Draft, dict]:
    """Core logic shared by all channel nodes. Returns (draft, llm_action)."""
    tone = state.get("tone", {})
    name     = state.get("target_name", "") or tone.get("name", "")
    company  = state.get("company", "their company")
    role     = state.get("role", "a professional")
    interests = ", ".join(tone.get("interests", []) or ["general topics"])
    recent   = tone.get("recent_activity_summary", "")

    # Derive first name from full name
    first_name = name.split()[0] if name else "there"

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
        name=name or "the target",
        first_name=first_name,
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
        logger.warning("[%s] JSON parse failed, trying fallback: %s", channel.upper(), exc)
        parse_status = "fallback"
        parse_error = str(exc)
        parsed = _extract_draft_fallback(raw_output, channel)
        if parsed.get("body"):
            parse_status = "success"  # fallback worked
            parse_error = None
        else:
            parse_status = "error"

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
