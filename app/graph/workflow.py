"""
app/graph/workflow.py
─────────────────────
LangGraph graph assembly.

Topology
────────
  START
    │
    ▼
  ingestion          (ephemeral data fetch + structure)
    │
    ▼
  persona            (tone analysis + vector DB lookup)
    │
    ├──────────────────────────────┐
    ▼                              ▼
  draft_email   draft_sms   draft_linkedin   draft_instagram
    │               │              │                │
    └───────────────┴──────────────┴────────────────┘
                    │
                    ▼
                 scoring        (score all 4 drafts in one call)
                    │
                    ▼
                 approval       (human-in-the-loop – interrupt / CLI)
                    │
                    ├── regen requested?  ──► back to the specific draft node(s)
                    │                          then scoring → approval again
                    ▼
                 execution      (Gmail / Twilio / mock)
                    │
                    ▼
                 persistence    (sanitise → Postgres + ChromaDB)
                    │
                    ▼
                  END

Regen loop
──────────
After approval, if state["regen_channels"] is non-empty, the
`_needs_regen` router sends us back to a "regen_drafts" node that
re-runs only the flagged channels, then back to scoring → approval.
A max-regen counter prevents infinite loops.
"""

from __future__ import annotations
import logging

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import OutreachState

# ── Node imports ──────────────────────────────────────────────────────────
from app.agents.ingestion_agent             import ingestion_node
from app.agents.persona_agent               import persona_node
from app.agents.draft_agents                import (
    draft_email_node, draft_sms_node,
    draft_linkedin_node, draft_instagram_node,
    draft_whatsapp_node,
    _generate_draft,                            # reused by regen
)
from app.agents.scoring_agent               import scoring_node
from app.agents.approval_and_persistence    import approval_node, persistence_node
from app.agents.execution_agent             import execution_node

logger = logging.getLogger(__name__)

MAX_REGEN_ROUNDS = 3   # safety cap


# ===========================================================================
# Regen node  –  re-generates only the channels the human flagged
# ===========================================================================

def regen_drafts_node(state: OutreachState) -> OutreachState:
    """
    Reads state["regen_channels"] and regenerates those drafts in place.
    Clears regen_channels afterwards so the next approval pass is clean.
    """
    regen_channels = state.get("regen_channels", [])
    logger.info("REGEN: channels=%s", regen_channels)

    updated_drafts = []
    new_llm_actions = []
    for d in state.get("drafts", []):
        if d["channel"] in regen_channels:
            # Re-generate this draft
            new_draft, llm_action = _generate_draft(d["channel"], state)
            updated_drafts.append(new_draft)
            new_llm_actions.append(llm_action)
            logger.info("[%s] Regenerated.", d["channel"].upper())
        else:
            updated_drafts.append(d)

    regen_count = state.get("regen_count", 0) + 1
    # Note: Since regen runs alone (not parallel), we can replace the entire drafts list
    # The add reducer only merges when multiple parallel nodes update the same field
    return {
        "drafts":          updated_drafts,
        "llm_actions":     new_llm_actions,
        "regen_channels":  [],
        "regen_count":     regen_count,
        "status":          "regen_done",
    }


# ===========================================================================
# Router functions  –  conditional edges
# ===========================================================================

def _needs_regen(state: OutreachState) -> str:
    """After approval: regen or proceed to execution?"""
    regen = state.get("regen_channels", [])
    count = state.get("regen_count", 0)

    if regen and count < MAX_REGEN_ROUNDS:
        return "regen_drafts"
    if regen and count >= MAX_REGEN_ROUNDS:
        logger.warning("Max regen rounds (%d) reached – forcing approval.", MAX_REGEN_ROUNDS)
    return "execution"


# ===========================================================================
# Graph builder
# ===========================================================================

def build_graph():
    """
    Assemble and compile the full LangGraph.
    Returns a compiled graph ready for .invoke() or .stream().
    """
    graph = StateGraph(OutreachState)

    # ── Add nodes ──────────────────────────────────────────────────────
    graph.add_node("ingestion",      ingestion_node)
    graph.add_node("persona",        persona_node)

    # Parallel draft nodes
    graph.add_node("draft_email",    draft_email_node)
    graph.add_node("draft_sms",      draft_sms_node)
    graph.add_node("draft_linkedin", draft_linkedin_node)
    graph.add_node("draft_instagram",draft_instagram_node)
    graph.add_node("draft_whatsapp", draft_whatsapp_node)

    graph.add_node("scoring",        scoring_node)
    graph.add_node("approval",       approval_node)
    graph.add_node("regen_drafts",   regen_drafts_node)
    graph.add_node("execution",      execution_node)
    graph.add_node("persistence",    persistence_node)

    # ── Edges ──────────────────────────────────────────────────────────

    # START → ingestion → persona
    graph.add_edge(START,        "ingestion")
    graph.add_edge("ingestion",  "persona")

    # persona → fan-out to all 5 draft nodes (parallel)
    graph.add_edge("persona",        "draft_email")
    graph.add_edge("persona",        "draft_sms")
    graph.add_edge("persona",        "draft_linkedin")
    graph.add_edge("persona",        "draft_instagram")
    graph.add_edge("persona",        "draft_whatsapp")

    # All 5 draft nodes → scoring  (fan-in)
    graph.add_edge("draft_email",    "scoring")
    graph.add_edge("draft_sms",      "scoring")
    graph.add_edge("draft_linkedin", "scoring")
    graph.add_edge("draft_instagram","scoring")
    graph.add_edge("draft_whatsapp", "scoring")

    # scoring → approval
    graph.add_edge("scoring",    "approval")

    # approval → conditional: regen_drafts OR execution
    graph.add_conditional_edges(
        "approval",
        _needs_regen,
        {
            "regen_drafts": "regen_drafts",
            "execution":    "execution",
        },
    )

    # regen_drafts → scoring  (re-score the fresh drafts)
    graph.add_edge("regen_drafts", "scoring")

    # execution → persistence → END
    graph.add_edge("execution",   "persistence")
    graph.add_edge("persistence", END)

    # ── Compile with checkpointer for interrupt/resume support ────────
    checkpointer = MemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("LangGraph compiled: nodes=%s", list(graph.nodes))
    return compiled
