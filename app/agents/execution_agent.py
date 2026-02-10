"""
app/agents/execution_agent.py
─────────────────────────────
STAGE 6 – Execution  (after human approval)

Routes each approved draft to the correct send tool:
  email     → app.tools.gmail_tool.send_gmail   (REAL)
  sms       → app.tools.twilio_tool.send_sms    (REAL)
  linkedin  → app.tools.mock_tool.mock_send     (MOCK – no API yet)
  instagram → app.tools.mock_tool.mock_send     (MOCK – no API yet)

The node expects two things in state:
  • drafts          – list of Draft dicts (with approved flag set)
  • approved_channels – list of channel names the human approved

Only drafts whose channel is in approved_channels AND approved==True
are actually sent.
"""

from __future__ import annotations
import logging
from typing import Any

from app.graph.state import OutreachState
from app.tools.gmail_tool  import send_gmail
from app.tools.twilio_tool import send_sms
from app.tools.mock_tool   import mock_send

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing table  –  channel → callable
# Each callable has the same signature:  (state_draft, ...) → result dict
# We wrap them so the interface is uniform.
# ---------------------------------------------------------------------------


def _route_email(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    """Gmail send.  Needs a 'to' address – taken from state links or prompt."""
    # In a real system you'd have the target email in state.
    # For now we pull it from links or fall back to a placeholder.
    to = state.get("links", {}).get("email", "target@example.com")
    return send_gmail(to=to, subject=draft.get("subject", "(no subject)"), body=draft["body"])


def _route_sms(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    """Twilio send.  Needs a phone number – from state or placeholder."""
    to_number = state.get("links", {}).get("phone", "+10000000000")
    return send_sms(to_number=to_number, body=draft["body"])


def _route_linkedin(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    to = state.get("links", {}).get("linkedin", "linkedin.com/in/target")
    return mock_send(channel="linkedin", to=to, body=draft["body"])


def _route_instagram(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    to = state.get("links", {}).get("instagram", "@target")
    return mock_send(channel="instagram", to=to, body=draft["body"])


def _route_whatsapp(draft: dict[str, Any], state: OutreachState) -> dict[str, Any]:
    """WhatsApp send.  Uses Twilio WhatsApp API or mock for now."""
    to_number = state.get("links", {}).get("whatsapp", "+10000000000")
    # Could use Twilio WhatsApp API (send_sms with whatsapp: prefix)
    # For prototype, use mock
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
