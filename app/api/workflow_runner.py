"""
app/api/workflow_runner.py
──────────────────────────
Async wrapper for running LangGraph workflows with real-time updates.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Any

from app.graph.workflow import build_graph
from app.api.state_manager import state_manager

logger = logging.getLogger(__name__)


async def run_campaign_workflow(campaign_id: str, raw_input: str, resume_from_interrupt: bool = False):
    """
    Run the full LangGraph workflow asynchronously with stage updates.
    
    Args:
        campaign_id: Unique ID for this campaign (used as thread_id)
        raw_input: Initial input data
        resume_from_interrupt: If True, resume from an interrupt point
    """
    try:
        # Build the graph (already compiled)
        graph = build_graph()
        
        # Configuration for checkpointing
        config = {"configurable": {"thread_id": campaign_id}}
        
        # If resuming from interrupt
        if resume_from_interrupt:
            campaign = state_manager.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found for resume")
                return
                
            current_state = campaign.get("state", {})
            approved_channels = current_state.get("approved_channels", [])
            regen_channels = current_state.get("regen_channels", [])
            
            logger.info(f"Resuming campaign {campaign_id}: approved={approved_channels}, regen={regen_channels}")
            
            # Try checkpoint-based resume first
            try:
                from langgraph.types import Command
                snapshot = graph.get_state(config)
                if snapshot and snapshot.next:
                    # Checkpoint exists - resume with Command
                    logger.info(f"Resuming from checkpoint, next nodes: {snapshot.next}")
                    
                    resume_value = {
                        "approved": approved_channels,
                        "regen": regen_channels,
                    }
                    
                    # Stream the resumed workflow
                    async for event in graph.astream(
                        Command(resume=resume_value),
                        config=config
                    ):
                        await _process_workflow_event(campaign_id, event, graph, config)
                    
                    # Mark completed
                    campaign = state_manager.get_campaign(campaign_id)
                    if campaign and campaign.get("state", {}).get("status") == "persisted":
                        campaign["status"] = "completed"
                    return
                    
            except Exception as e:
                logger.warning(f"Checkpoint resume failed for {campaign_id}: {e}")
            
            # Fallback: manual continuation
            await _manual_workflow_continuation(graph, campaign_id, current_state, config)
            return
        else:
            # New workflow
            input_value = {"raw_input": raw_input}
        
        # Stream through the workflow with config for checkpointing
        async for event in graph.astream(input_value, config=config):
            await _process_workflow_event(campaign_id, event, graph, config)
        
        # Final update
        campaign = state_manager.get_campaign(campaign_id)
        if campaign:
            final_state = campaign["state"]
            if final_state.get("status") == "persisted":
                state_manager.update_stage(
                    campaign_id, "persistence", "completed",
                    "Campaign completed successfully"
                )
                campaign["status"] = "completed"
            
    except Exception as exc:
        logger.error(f"Campaign {campaign_id} failed: {exc}", exc_info=True)
        campaign = state_manager.get_campaign(campaign_id)
        current_stage = "unknown"
        if campaign:
            current_stage = campaign.get("current_stage", "unknown")
        state_manager.update_stage(campaign_id, current_stage, "failed", str(exc))
        if campaign:
            campaign["status"] = "failed"
            campaign["error"] = str(exc)


async def _process_workflow_event(campaign_id: str, event: dict, graph, config: dict):
    """Process a single workflow stream event and update state manager."""
    # Stage mapping
    stage_map = {
        "ingestion": "ingestion",
        "persona": "persona",
        "draft_email": "drafting",
        "draft_sms": "drafting",
        "draft_linkedin": "drafting",
        "draft_instagram": "drafting",
        "draft_whatsapp": "drafting",
        "regen_drafts": "drafting",
        "approval": "approval",
        "execution": "execution",
        "persistence": "persistence",
    }
    
    logger.info(f"Campaign {campaign_id} event: {list(event.keys())}")
    
    for node_name, node_state in event.items():
        # Handle LangGraph interrupt event
        if node_name == "__interrupt__":
            logger.info(f"Campaign {campaign_id} reached approval interrupt")
            state_manager.update_stage(
                campaign_id, "approval", "waiting",
                "Waiting for user approval of generated drafts"
            )
            return
        
        # Skip system events
        if node_name.startswith("__"):
            continue
        
        if not isinstance(node_state, dict):
            continue
        
        # Map node to stage
        stage = stage_map.get(node_name, node_name)
        
        state_manager.update_stage(
            campaign_id, stage, "running",
            f"Processing {stage}..."
        )
        
        # Update full state
        state_manager.update_state(campaign_id, node_state)
        
        # Mark stage as completed
        state_manager.update_stage(
            campaign_id, stage, "completed",
            f"{stage.capitalize()} completed"
        )


async def _manual_workflow_continuation(graph, campaign_id: str, current_state: dict, config: dict):
    """
    Manually continue workflow from approval for campaigns without checkpoints.
    Handles both approve-to-execute and regen flows.
    """
    from app.agents.approval_and_persistence import persistence_node
    from app.agents.execution_agent import execution_node
    from app.graph.workflow import regen_drafts_node, MAX_REGEN_ROUNDS
    
    try:
        logger.info(f"Manually continuing workflow for campaign {campaign_id}")

        # Guard: if campaign is already completed or further along, skip
        existing_campaign = state_manager.get_campaign(campaign_id)
        if existing_campaign and existing_campaign.get("status") in ("completed", "executed", "persisted"):
            logger.warning(f"Campaign {campaign_id} already completed/executed – skipping duplicate resume")
            return

        # Apply approval decisions to drafts
        approved_channels = current_state.get("approved_channels", [])
        regen_channels = current_state.get("regen_channels", [])

        updated_drafts = []
        for d in current_state.get("drafts", []):
            if d["channel"] in approved_channels:
                d = {**d, "approved": True}
            updated_drafts.append(d)
        current_state["drafts"] = updated_drafts
        current_state["status"] = "approved"

        state_manager.update_stage(campaign_id, "approval", "completed", "Approval completed")
        state_manager.update_state(campaign_id, current_state)

        # Handle regeneration loop
        regen_count = current_state.get("regen_count", 0)
        while regen_channels and regen_count < MAX_REGEN_ROUNDS:
            logger.info(f"Regenerating channels: {regen_channels}")
            state_manager.update_stage(campaign_id, "drafting", "running", f"Regenerating {', '.join(regen_channels)}...")

            regen_result = regen_drafts_node(current_state)
            if regen_result:
                # Merge regen results into state
                current_state["drafts"] = regen_result.get("drafts", current_state["drafts"])
                current_state["regen_channels"] = regen_result.get("regen_channels", [])
                current_state["regen_count"] = regen_result.get("regen_count", regen_count + 1)
                if regen_result.get("llm_actions"):
                    current_state.setdefault("llm_actions", []).extend(regen_result["llm_actions"])
            
            state_manager.update_stage(campaign_id, "drafting", "completed", "Regeneration completed")
            state_manager.update_state(campaign_id, current_state)

            # Return to approval - let the frontend handle the new drafts
            state_manager.update_stage(campaign_id, "approval", "waiting", "Waiting for approval of regenerated drafts")
            current_state["status"] = "approval"
            state_manager.update_state(campaign_id, current_state)
            
            campaign = state_manager.get_campaign(campaign_id)
            if campaign:
                campaign["status"] = "approval"
                campaign["current_stage"] = "approval"
            return
        
        # Run execution node
        state_manager.update_stage(campaign_id, "execution", "running", "Executing approved channels...")
        execution_result = execution_node(current_state)
        if execution_result:
            # Use a shallow copy to avoid same-object-reference issues in update_state
            state_manager.update_state(campaign_id, dict(execution_result))
        state_manager.update_stage(campaign_id, "execution", "completed", "Execution completed")
        
        # Run persistence node
        state_manager.update_stage(campaign_id, "persistence", "running", "Persisting results...")
        persistence_result = persistence_node(current_state)
        if persistence_result:
            state_manager.update_state(campaign_id, dict(persistence_result))
        state_manager.update_stage(campaign_id, "persistence", "completed", "Campaign completed successfully")
        
        # Mark campaign as completed (explicitly, so frontend polling stops)
        state_manager.update_state(campaign_id, {"status": "completed"})
        campaign = state_manager.get_campaign(campaign_id)
        if campaign:
            campaign["status"] = "completed"
        
        logger.info(f"Campaign {campaign_id} completed successfully via manual continuation")
        
    except Exception as exc:
        logger.error(f"Manual workflow continuation failed for campaign {campaign_id}: {exc}", exc_info=True)
        state_manager.update_stage(
            campaign_id, "execution", "failed", str(exc)
        )
        campaign = state_manager.get_campaign(campaign_id)
        if campaign:
            campaign["status"] = "failed"
            campaign["error"] = str(exc)
