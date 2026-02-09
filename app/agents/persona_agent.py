"""
app/agents/persona_agent.py
───────────────────────────
STAGE 2 – Persona Analysis

This is the "deep-think" node.  It:
  1. Queries the vector store for similar past personas → richer context.
  2. Builds a detailed, structured prompt asking the LLM to derive:
       • formality level
       • communication style summary
       • language / tone hints
       • inferred interests
       • recent-activity summary
  3. Calls the local Ollama LLM.
  4. Parses the JSON output into state["tone"].
  5. **Deletes** raw_profile_text from state (ephemeral – never persisted).
"""

from __future__ import annotations
import json
import logging
import re
import time
from typing import Any

from langchain_ollama import OllamaLLM

from app.config import settings
from app.db.vector_store import query_similar_personas
from app.graph.state import OutreachState, create_llm_action, add_llm_action, start_stage, complete_stage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM (singleton)
# ---------------------------------------------------------------------------
_llm: OllamaLLM | None = None


def _get_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=settings.ollama.model,
            base_url=settings.ollama.base_url,
            temperature=0.2,            # low – we want analytical, not creative here
            num_predict=1024,
        )
        logger.info("Persona LLM initialised: model=%s", settings.ollama.model)
    return _llm


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_PERSONA_PROMPT_TEMPLATE = """You are an expert communication-style analyst.

Given the following publicly available profile text about a professional,
derive a detailed tone & style profile. Your output MUST be valid JSON
with EXACTLY these keys – no extra text before or after the JSON block:

{{
  "formality_level": "<casual | semi-formal | formal>",
  "communication_style": "<2-3 sentence description of how this person writes/communicates>",
  "language_hints": "<specific quirks: emoji use, abbreviations, sentence length, punctuation habits>",
  "interests": ["<interest1>", "<interest2>", ...],
  "recent_activity_summary": "<1-2 sentence summary of what they have been doing lately – no names or emails>",
  "tone_keywords": ["<word1>", "<word2>", ...]
}}

─── CONTEXT: Similar profiles from past outreach (learn from these) ───
{similar_context}

─── TARGET PROFILE TEXT ───
{profile_text}

─── INSTRUCTIONS ───
• Analyse word choice, sentence structure, punctuation and emoji usage.
• If the text is short, make reasonable inferences from the role + industry.
• Keep recent_activity_summary factual and PII-free (no full names or emails).
• Return ONLY the JSON object. No markdown fences. No explanation.
"""


def _build_prompt(profile_text: str, similar_personas: list[dict[str, Any]]) -> str:
    # Format similar personas into readable context
    if similar_personas:
        ctx_lines = []
        for i, sp in enumerate(similar_personas, 1):
            ctx_lines.append(
                f"  [{i}] (industry={sp.get('industry', 'unknown')}, "
                f"similarity={sp.get('similarity', 0)})\n"
                f"      {sp.get('tone_summary', '')}"
            )
        similar_context = "\n".join(ctx_lines)
    else:
        similar_context = "  (none – this is the first run or no similar profiles exist yet)"

    return _PERSONA_PROMPT_TEMPLATE.format(
        similar_context=similar_context,
        profile_text=profile_text,
    )


# ---------------------------------------------------------------------------
# JSON extraction helper  (robust to LLM adding markdown fences etc.)
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any]:
    """Pull the first JSON object out of raw LLM output."""
    # Strip common markdown fences
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned)
    cleaned = cleaned.strip()

    # Find the first { … } block
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM output")
    # Find matching closing brace
    depth = 0
    end = start
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return json.loads(cleaned[start:end])


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------

def persona_node(state: OutreachState) -> OutreachState:
    logger.info("=== PERSONA ANALYSIS START ===")
    
    # Start stage tracking
    state = start_stage(state, "persona")

    profile_text: str = state.get("raw_profile_text", "")
    if not profile_text:
        logger.warning("No raw_profile_text – persona analysis will be shallow.")

    # ── 1. Pull similar personas from vector DB ─────────────────────
    # We use company + role + industry as a rough query string
    query_str = " ".join(filter(None, [
        state.get("company", ""),
        state.get("role", ""),
        state.get("industry", ""),
        "communication style tone",
    ]))
    similar = query_similar_personas(query_str, top_k=3)
    logger.info("Found %d similar personas in vector store.", len(similar))

    # ── 2. Build prompt & call LLM ───────────────────────────────────
    prompt = _build_prompt(profile_text, similar)
    llm = _get_llm()

    logger.info("Calling Ollama for persona analysis …")
    start_time = time.time()
    raw_output: str = llm.invoke(prompt)
    duration_ms = int((time.time() - start_time) * 1000)
    logger.debug("Raw LLM output:\n%s", raw_output)

    # ── 3. Parse JSON ────────────────────────────────────────────────
    parse_status = "success"
    parse_error = None
    try:
        tone_json = _extract_json(raw_output)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Failed to parse persona JSON: %s\nRaw: %s", exc, raw_output)
        parse_status = "error"
        parse_error = str(exc)
        # Fallback: store raw text as a single-field dict so pipeline doesn't crash
        tone_json = {
            "formality_level": "unknown",
            "communication_style": raw_output[:500],
            "language_hints": "",
            "interests": [],
            "recent_activity_summary": "",
            "tone_keywords": [],
        }

    # ── 4. Log LLM action ────────────────────────────────────────────
    llm_action = create_llm_action(
        stage="persona",
        agent="persona_agent",
        action="Analyzing profile to extract communication style and persona",
        model=settings.ollama.model,
        prompt=prompt,
        response=raw_output,
        duration_ms=duration_ms,
        status=parse_status,
        error_message=parse_error,
    )
    state = add_llm_action(state, llm_action)

    # ── 5. Update state & DELETE ephemeral raw text ──────────────────
    # Complete stage tracking
    state = complete_stage(state, "persona")
    
    updated: OutreachState = {
        **state,
        "tone":              tone_json,
        "similar_personas":  similar,
        "status":            "persona_done",
        # ── EPHEMERAL CLEANUP ──
        "raw_profile_text":  "",   # cleared – never reaches persistence
        "raw_input":         "",   # cleared
    }

    logger.info("Persona done | formality=%s keywords=%s",
                tone_json.get("formality_level"),
                tone_json.get("tone_keywords"))
    return updated
