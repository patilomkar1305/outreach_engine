"""
app/api/state_manager.py
─────────────────────────
In-memory state management for single-user prototype.
Stores active campaigns, sessions, and provides async event streaming.
"""

from __future__ import annotations
import asyncio
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Any
import logging

logger = logging.getLogger(__name__)

# Directory for session persistence
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)


class StateManager:
    """Manages campaign state, sessions, and event broadcasting."""
    
    def __init__(self):
        self.campaigns: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.event_queues: dict[str, list[asyncio.Queue]] = {}
        
        # Load existing sessions from disk
        self._load_sessions()
    
    def _load_sessions(self):
        """Load all sessions from disk on startup."""
        try:
            for session_file in SESSIONS_DIR.glob("*.json"):
                with open(session_file, "r") as f:
                    session_data = json.load(f)
                    session_id = session_data.get("session_id")
                    if session_id:
                        self.sessions[session_id] = session_data
                        # Recreate campaigns from session
                        for campaign in session_data.get("campaigns", []):
                            self.campaigns[campaign["id"]] = campaign
                        logger.info(f"Loaded session {session_id} with {len(session_data.get('campaigns', []))} campaigns")
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
    
    def _save_session(self, session_id: str):
        """Save a session to disk."""
        try:
            session = self.sessions.get(session_id)
            if session:
                session_file = SESSIONS_DIR / f"{session_id}.json"
                with open(session_file, "w") as f:
                    json.dump(session, f, indent=2, default=str)
                logger.debug(f"Saved session {session_id}")
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
    
    def create_session(self, name: str | None = None) -> str:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        
        self.sessions[session_id] = {
            "session_id": session_id,
            "name": name or f"Session {len(self.sessions) + 1}",
            "created_at": now,
            "updated_at": now,
            "campaigns": []
        }
        
        self._save_session(session_id)
        logger.info(f"Created session {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with summaries."""
        summaries = []
        for session in self.sessions.values():
            campaigns = session.get("campaigns", [])
            last_campaign = campaigns[-1] if campaigns else None
            
            summaries.append({
                "session_id": session["session_id"],
                "name": session["name"],
                "created_at": session["created_at"],
                "updated_at": session["updated_at"],
                "campaign_count": len(campaigns),
                "last_company": last_campaign.get("state", {}).get("company") if last_campaign else None,
                "last_role": last_campaign.get("state", {}).get("role") if last_campaign else None,
            })
        
        # Sort by updated_at descending
        summaries.sort(key=lambda x: x["updated_at"], reverse=True)
        return summaries
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its campaigns."""
        if session_id in self.sessions:
            # Remove campaigns
            for campaign in self.sessions[session_id].get("campaigns", []):
                if campaign["id"] in self.campaigns:
                    del self.campaigns[campaign["id"]]
            
            del self.sessions[session_id]
            
            # Delete file
            session_file = SESSIONS_DIR / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            
            logger.info(f"Deleted session {session_id}")
            return True
        return False
    
    def create_campaign(self, input_data: dict[str, Any], session_id: str | None = None) -> str:
        """Create a new campaign and return its ID."""
        campaign_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Create or use existing session
        if not session_id:
            session_id = self.create_session()
        elif session_id not in self.sessions:
            session_id = self.create_session()
        
        campaign = {
            "id": campaign_id,
            "session_id": session_id,
            "status": "created",
            "current_stage": "pending",
            "input": input_data,
            "state": {
                "llm_actions": [],
                "stages": [],
                "drafts": [],
            },
            "created_at": now.isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "stages": {
                "ingestion": {"status": "pending", "message": ""},
                "persona": {"status": "pending", "message": ""},
                "drafting": {"status": "pending", "message": ""},
                "scoring": {"status": "pending", "message": ""},
                "approval": {"status": "pending", "message": ""},
                "execution": {"status": "pending", "message": ""},
                "persistence": {"status": "pending", "message": ""},
            }
        }
        
        self.campaigns[campaign_id] = campaign
        self.event_queues[campaign_id] = []
        
        # Add to session
        self.sessions[session_id]["campaigns"].append(campaign)
        self.sessions[session_id]["updated_at"] = now.isoformat() + "Z"
        self._save_session(session_id)
        
        logger.info(f"Created campaign {campaign_id} in session {session_id}")
        return campaign_id
    
    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        """Get campaign by ID."""
        return self.campaigns.get(campaign_id)
    
    def update_stage(self, campaign_id: str, stage: str, status: str, message: str = ""):
        """Update a specific stage status."""
        if campaign_id in self.campaigns:
            now = datetime.utcnow()
            self.campaigns[campaign_id]["stages"][stage] = {
                "status": status,
                "message": message,
                "timestamp": now
            }
            self.campaigns[campaign_id]["current_stage"] = stage
            self.campaigns[campaign_id]["updated_at"] = now.isoformat() + "Z"
            
            # Update session
            session_id = self.campaigns[campaign_id].get("session_id")
            if session_id:
                self.sessions[session_id]["updated_at"] = now.isoformat() + "Z"
                self._save_session(session_id)
            
            # Broadcast event
            event = {
                "type": "stage_update",
                "stage": stage,
                "status": status,
                "message": message,
                "timestamp": now.isoformat() + "Z"
            }
            asyncio.create_task(self._broadcast_event(campaign_id, event))
    
    def update_state(self, campaign_id: str, state: dict[str, Any]):
        """Update the full LangGraph state."""
        if campaign_id in self.campaigns:
            now = datetime.utcnow()
            self.campaigns[campaign_id]["state"] = state
            self.campaigns[campaign_id]["status"] = state.get("status", "running")
            self.campaigns[campaign_id]["updated_at"] = now.isoformat() + "Z"
            
            # Update session
            session_id = self.campaigns[campaign_id].get("session_id")
            if session_id:
                self.sessions[session_id]["updated_at"] = now.isoformat() + "Z"
                # Update the campaign in session's campaigns list
                for i, c in enumerate(self.sessions[session_id]["campaigns"]):
                    if c["id"] == campaign_id:
                        self.sessions[session_id]["campaigns"][i] = self.campaigns[campaign_id]
                        break
                self._save_session(session_id)
            
            # Broadcast LLM actions if any
            llm_actions = state.get("llm_actions", [])
            if llm_actions:
                event = {
                    "type": "llm_actions_update",
                    "actions": llm_actions,
                    "timestamp": now.isoformat() + "Z"
                }
                asyncio.create_task(self._broadcast_event(campaign_id, event))
    
    async def _broadcast_event(self, campaign_id: str, event: dict[str, Any]):
        """Broadcast event to all subscribers."""
        if campaign_id in self.event_queues:
            for queue in self.event_queues[campaign_id]:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.error(f"Failed to broadcast event: {e}")
    
    def subscribe(self, campaign_id: str) -> asyncio.Queue:
        """Subscribe to campaign events."""
        queue = asyncio.Queue()
        if campaign_id not in self.event_queues:
            self.event_queues[campaign_id] = []
        self.event_queues[campaign_id].append(queue)
        return queue
    
    def unsubscribe(self, campaign_id: str, queue: asyncio.Queue):
        """Unsubscribe from campaign events."""
        if campaign_id in self.event_queues:
            try:
                self.event_queues[campaign_id].remove(queue)
            except ValueError:
                pass


# Global singleton for single-user prototype
state_manager = StateManager()
