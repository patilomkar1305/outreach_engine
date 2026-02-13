"""
app/agents/execution_agent.py
─────────────────────────────
STAGE 6 – Execution  (after human approval)

Routes each approved draft to the correct send tool:
  email     → app.tools.gmail_tool.send_gmail   (REAL) or mock if not configured
  sms       → app.tools.twilio_tool.send_sms    (REAL) or mock if not configured
  linkedin  → app.tools.mock_tool.mock_send     (MOCK – no API yet)
  instagram → app.tools.mock_tool.mock_send     (MOCK – no API yet)
  whatsapp  → app.tools.mock_tool.mock_send     (MOCK – no API yet)

Falls back to mock_send automatically when credentials are not configured
in .env, so the pipeline never crashes on unconfigured channels.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

from app.config import settings
from app.graph.state import OutreachState
from app.tools.mock_tool   import mock_send

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Credential checks
# ---------------------------------------------------------------------------

def _gmail_configured() -> bool:
    """Check if Gmail credentials exist."""
    creds_path = Path(settings.gmail.credentials_path)
    token_path = Path(settings.gmail.token_path)
    return creds_path.exists() or token_path.exists()


def _twilio_configured() -> bool:
    """Check if Twilio credentials are set in .env."""
    return bool(
        settings.twilio.account_sid
        and settings.twilio.auth_token
        and settings.twilio.from_number
    )


# ---------------------------------------------------------------------------
# Routing table  –  channel → callable
# ---------------------------------------------------------------------------

def _route_email(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    """Gmail send with fallback to mock if not configured."""
    to = state.get("links", {}).get("email", "target@example.com")
    
    if _gmail_configured():
        try:
            from app.tools.gmail_tool import send_gmail
            result = send_gmail(to=to, subject=draft.get("subject", "(no subject)"), body=draft["body"])
            if result.get("status") != "error":
                return result
            logger.warning("Gmail send failed, falling back to mock: %s", result.get("error"))
        except Exception as exc:
            logger.warning("Gmail import/send failed, falling back to mock: %s", exc)
    else:
        logger.info("Gmail not configured (.env missing credentials) – using mock send")
    
    return mock_send(channel="email", to=to, body=draft["body"], subject=draft.get("subject"))


def _route_sms(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    """Twilio send with fallback to mock if not configured."""
    to_number = state.get("links", {}).get("phone", "+10000000000")
    
    if _twilio_configured():
        try:
            from app.tools.twilio_tool import send_sms
            result = send_sms(to_number=to_number, body=draft["body"])
            if result.get("status") != "error":
                return result
            logger.warning("Twilio send failed, falling back to mock: %s", result.get("error"))
        except Exception as exc:
            logger.warning("Twilio import/send failed, falling back to mock: %s", exc)
    else:
        logger.info("Twilio not configured (.env missing credentials) – using mock send")
    
    return mock_send(channel="sms", to=to_number, body=draft["body"])


def _route_linkedin(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    to = state.get("links", {}).get("linkedin", "linkedin.com/in/target")
    return mock_send(channel="linkedin", to=to, body=draft["body"])


def _route_instagram(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    to = state.get("links", {}).get("instagram", "@target")
    return mock_send(channel="instagram", to=to, body=draft["body"])


def _route_whatsapp(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    """WhatsApp send – mock for now."""
    to_number = state.get("links", {}).get("whatsapp", "+10000000000")
    return mock_send(channel="whatsapp", to=to_number, body=draft["body"])


ROUTER: dict[str, Any] = {
    "email":     _route_email,
    "sms":       _route_sms,
    "linkedin":  _route_linkedin,
    "instagram": _route_instagram,
    "whatsapp":  _route_whatsapp,
}


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------

def execution_node(state: OutreachState) -> OutreachState:
    logger.info("=== EXECUTION START ===")

    drafts            = state.get("drafts", [])
    approved_channels = state.get("approved_channels", [])
    results: list[dict[str, Any]] = []

    for draft in drafts:
        channel = draft["channel"]

        # Only send if the human approved this channel
        if channel not in approved_channels:
            logger.info("[%s] Skipped – not approved.", channel.upper())
            continue

        route_fn = ROUTER.get(channel)
        if route_fn is None:
            logger.warning("[%s] No router registered – skipping.", channel.upper())
            continue

        logger.info("[%s] Sending …", channel.upper())
        result = route_fn(draft, state)
        result["channel"] = channel
        results.append(result)

        # Mark draft as sent in state
        draft["sent"] = True

    logger.info("Execution complete. Results: %s", results)
    return {"execution_results": results, "status": "executed"}
