"""
app/agents/scoring_agent.py
───────────────────────────
STAGE 4 – Scoring

Sends ALL drafts to the LLM in a single prompt so the model can
compare them and score consistently.  Each draft gets a 0-10 score
and a short rationale.

Scores are written back into each Draft dict so the approval node
can surface them to the human.
"""

from __future__ import annotations
import json
import logging
import re
import time
from typing import Any

from langchain_ollama import OllamaLLM

from app.config import settings
from app.graph.state import OutreachState, create_llm_action, add_llm_action, start_stage, complete_stage

logger = logging.getLogger(__name__)

_llm: OllamaLLM | None = None


def _get_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=settings.ollama.model,
            base_url=settings.ollama.base_url,
            temperature=0.1,        # very low – scoring should be deterministic
            num_predict=768,
        )
    return _llm


_SCORING_PROMPT = """You are a cold-outreach quality judge.

Score each of the following drafts on a scale of 0-10 based on:
  • Personalisation  (does it feel tailored, not generic?)
  • Tone match       (does it match the persona's style?)
  • CTA clarity      (is the call-to-action clear and compelling?)
  • Natural writing  (does it sound human, not AI-generated?)

─── PERSONA TONE ───
{tone_summary}

─── DRAFTS ───
{drafts_block}

─── OUTPUT FORMAT ───
Return ONLY a JSON array – one object per draft, same order as input.
No markdown. No explanation outside the JSON.

[
  {{
    "channel": "<channel name>",
    "score": <0-10 float>,
    "rationale": "<1-2 sentences explaining the score>"
  }},
  ...
]
"""


def scoring_node(state: OutreachState) -> OutreachState:
    logger.info("=== SCORING START ===")
    
    # Start stage tracking
    state = start_stage(state, "scoring")

    drafts = state.get("drafts", [])
    if not drafts:
        logger.warning("No drafts to score.")
        state = complete_stage(state, "scoring")
        return {**state, "status": "scored"}

    tone = state.get("tone", {})

    # Build the drafts block for the prompt
    drafts_block_parts: list[str] = []
    for i, d in enumerate(drafts, 1):
        header = f"[{i}] Channel: {d['channel']}"
        if d.get("subject"):
            header += f" | Subject: {d['subject']}"
        drafts_block_parts.append(f"{header}\n{d['body']}")
    drafts_block = "\n\n".join(drafts_block_parts)

    prompt = _SCORING_PROMPT.format(
        tone_summary=json.dumps(tone, indent=2),
        drafts_block=drafts_block,
    )

    llm = _get_llm()
    logger.info("Calling Ollama for scoring …")
    start_time = time.time()
    raw_output = llm.invoke(prompt)
    duration_ms = int((time.time() - start_time) * 1000)
    logger.debug("Scoring raw output:\n%s", raw_output)

    # ── Parse JSON array ───────────────────────────────────────────
    parse_status = "success"
    parse_error = None
    try:
        cleaned = raw_output.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned)
        cleaned = re.sub(r"```$", "", cleaned)
        cleaned = cleaned.strip()

        start = cleaned.find("[")
        end   = cleaned.rfind("]") + 1
        scores_list: list[dict[str, Any]] = json.loads(cleaned[start:end])
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Score parsing failed: %s\nRaw: %s", exc, raw_output)
        parse_status = "error"
        parse_error = str(exc)
        scores_list = []

    # ── Log LLM action ─────────────────────────────────────────────
    llm_action = create_llm_action(
        stage="scoring",
        agent="scoring_agent",
        action=f"Evaluating {len(drafts)} drafts for quality and personalization",
        model=settings.ollama.model,
        prompt=prompt,
        response=raw_output,
        duration_ms=duration_ms,
        status=parse_status,
        error_message=parse_error,
    )
    state = add_llm_action(state, llm_action)

    # ── Map scores back onto drafts by channel ────────────────────
    score_map: dict[str, dict[str, Any]] = {}
    for s in scores_list:
        ch = s.get("channel", "").strip().lower()
        score_map[ch] = s

    updated_drafts = []
    for d in drafts:
        ch = d["channel"].lower()
        if ch in score_map:
            d = {
                **d, 
                "score": score_map[ch].get("score", 0),
                "score_rationale": score_map[ch].get("rationale", "")
            }
        updated_drafts.append(d)

    # Pretty-print scores for the user
    logger.info("Scores: %s", {d["channel"]: d.get("score") for d in updated_drafts})

    # Complete stage tracking
    state = complete_stage(state, "scoring")
    
    return {**state, "drafts": updated_drafts, "status": "scored"}
