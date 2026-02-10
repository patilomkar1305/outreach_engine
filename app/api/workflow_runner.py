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
        
        # If resuming from interrupt (backward compatibility for campaigns without checkpoints)
        if resume_from_interrupt:
            campaign = state_manager.get_campaign(campaign_id)
            if campaign:
                current_state = campaign.get("state", {})
                
                # Try to check if checkpoint exists
                try:
                    snapshot = graph.get_state(config)
                    if snapshot and snapshot.next:
                        # Checkpoint exists, resume normally
                        logger.info(f"Resuming campaign {campaign_id} from checkpoint")
                        input_value = None
                    else:
                        # No checkpoint - manually continue from approval node
                        logger.warning(f"No checkpoint for campaign {campaign_id}, manually continuing workflow")
                        # Manually invoke approval and subsequent nodes
                        await _manual_workflow_continuation(graph, campaign_id, current_state, config)
                        return
                except Exception as e:
                    # Checkpoint doesn't exist - manually continue
                    logger.warning(f"Checkpoint error for campaign {campaign_id}: {e}, manually continuing")
                    await _manual_workflow_continuation(graph, campaign_id, current_state, config)
                    return
        else:
            # New workflow
            input_value = {"raw_input": raw_input}
        
        # Stage mapping
        stage_map = {
            "ingestion": "ingestion",
            "persona": "persona",
            "draft_email": "drafting",
            "draft_sms": "drafting",
            "draft_linkedin": "drafting",
            "draft_instagram": "drafting",
            "scoring": "scoring",
            "approval": "approval",
            "execution": "execution",
            "persistence": "persistence",
        }
        
        current_drafting = False
        
        # Stream through the workflow with config for checkpointing
        async for event in graph.astream(input_value, config=config):
            logger.info(f"Campaign {campaign_id} event: {list(event.keys())}")
            
            for node_name, node_state in event.items():
                # Handle LangGraph interrupt event - indicates approval stage
                if node_name == "__interrupt__":
                    logger.info(f"Campaign {campaign_id} reached approval interrupt")
                    state_manager.update_stage(
                        campaign_id, "approval", "waiting",
                        "Waiting for user approval of generated drafts"
                    )
                    # Workflow is paused - frontend will handle approval
                    return
                
                # Skip other LangGraph system events (like __start__, __end__, etc.)
                if node_name.startswith("__"):
                    logger.debug(f"Skipping system event: {node_name}")
                    continue
                
                # Ensure node_state is a dict (defensive check)
                if not isinstance(node_state, dict):
                    logger.error(f"Node {node_name} returned non-dict state: {type(node_state)}")
                    continue
                
                # Map node to stage
                stage = stage_map.get(node_name, node_name)
                
                # Handle drafting nodes specially (all 5 run in parallel)
                if stage == "drafting":
                    if not current_drafting:
                        state_manager.update_stage(
                            campaign_id, "drafting", "running",
                            "Generating personalized drafts for all channels..."
                        )
                        current_drafting = True
                else:
                    current_drafting = False
                    state_manager.update_stage(
                        campaign_id, stage, "running",
                        f"Processing {stage}..."
                    )
                
                # Update full state
                state_manager.update_state(campaign_id, node_state)
                
                # Mark stage as completed
                if stage != "drafting" or (stage == "drafting" and "draft_instagram" in event):
                    state_manager.update_stage(
                        campaign_id, stage, "completed",
                        f"{stage.capitalize()} completed"
                    )
        
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
        state_manager.update_stage(
            campaign_id, state_manager.get_campaign(campaign_id)["current_stage"],
            "failed", str(exc)
        )
        campaign = state_manager.get_campaign(campaign_id)
        if campaign:
            campaign["status"] = "failed"
            campaign["error"] = str(exc)


async def _manual_workflow_continuation(graph, campaign_id: str, current_state: dict, config: dict):
    """
    Manually continue workflow from approval for campaigns without checkpoints.
    This provides backward compatibility for campaigns started before checkpointer was added.
    """
    from app.agents.approval_and_persistence import approval_node, persistence_node
    from app.agents.execution_agent import execution_node
    
    try:
        logger.info(f"Manually continuing workflow for campaign {campaign_id}")
        
        # Run approval node
        state_manager.update_stage(campaign_id, "approval", "running", "Processing approval...")
        approval_result = approval_node(current_state)
        if approval_result:
            current_state.update(approval_result)
            state_manager.update_state(campaign_id, current_state)
        state_manager.update_stage(campaign_id, "approval", "completed", "Approval completed")
        
        # Check if regeneration is needed
        if current_state.get("regen_channels"):
            logger.info(f"Regeneration requested for channels: {current_state['regen_channels']}")
            # For now, skip regeneration in manual mode
            # In a real implementation, you'd call regen_drafts_node here
        
        # Run execution node
        state_manager.update_stage(campaign_id, "execution", "running", "Executing approved channels...")
        execution_result = execution_node(current_state)
        if execution_result:
            current_state.update(execution_result)
            state_manager.update_state(campaign_id, current_state)
        state_manager.update_stage(campaign_id, "execution", "completed", "Execution completed")
        
        # Run persistence node
        state_manager.update_stage(campaign_id, "persistence", "running", "Persisting results...")
        persistence_result = persistence_node(current_state)
        if persistence_result:
            current_state.update(persistence_result)
            state_manager.update_state(campaign_id, current_state)
        state_manager.update_stage(campaign_id, "persistence", "completed", "Campaign completed successfully")
        
        # Update campaign status
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
