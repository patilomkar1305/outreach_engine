"""
app/api/main.py
───────────────
FastAPI application entry point.
"""

from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.api.schemas import (
    CampaignStartRequest, CampaignResponse,
    DraftResponse, DraftActionRequest, StageUpdate,
    LLMActionResponse, StageInfoResponse, PersonaResponse,
    SessionSummary, SessionDetail, SessionCreateRequest
)
from app.api.state_manager import state_manager
from app.api.workflow_runner import run_campaign_workflow
from app.utils.llm import check_ollama_health, get_model_info, list_recommended_models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Outreach Engine API",
    version="1.0.0",
    description="LLM-powered hyper-personalized cold outreach automation"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite/React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory for files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _build_campaign_response(campaign: dict, campaign_id: str) -> CampaignResponse:
    """Build a CampaignResponse from campaign data."""
    state = campaign.get("state", {})
    
    # Defensive check: ensure state is a dict
    if not isinstance(state, dict):
        logger.error(f"Campaign {campaign_id} has invalid state type: {type(state)}")
        state = {}
    
    drafts_data = state.get("drafts", [])
    llm_actions_data = state.get("llm_actions", [])
    tone = state.get("tone", {})
    
    # Build stages from the top-level campaign stages dict
    # (update_stage() writes here, NOT to state["stages"])
    campaign_stages = campaign.get("stages", {})
    
    # Build drafts response
    drafts = [
        DraftResponse(
            id=d.get("id"),
            channel=d["channel"],
            subject=d.get("subject"),
            body=d["body"],
            score=d.get("score"),
            score_rationale=d.get("score_rationale"),
            approved=d.get("approved", False),
            sent=d.get("sent", False),
            version=d.get("version", 1),
            regenerate_count=d.get("regenerate_count", 0),
            created_at=d.get("created_at")
        )
        for d in drafts_data
    ]
    
    # Build LLM actions response
    llm_actions = [
        LLMActionResponse(
            id=a.get("id", ""),
            timestamp=a.get("timestamp", ""),
            stage=a.get("stage", ""),
            agent=a.get("agent", ""),
            action=a.get("action", ""),
            model=a.get("model", ""),
            prompt_preview=a.get("prompt_preview", ""),
            response_preview=a.get("response_preview", ""),
            tokens_used=a.get("tokens_used"),
            duration_ms=a.get("duration_ms", 0),
            status=a.get("status", ""),
            error_message=a.get("error_message")
        )
        for a in llm_actions_data
    ]
    
    # Build stages response from the top-level stages dict
    stages = []
    for stage_cfg in [
        "ingestion", "persona", "drafting", "approval",
        "execution", "persistence",
    ]:
        sd = campaign_stages.get(stage_cfg, {})
        ts = sd.get("timestamp")
        started_str = ts.isoformat() + "Z" if hasattr(ts, 'isoformat') else str(ts) if ts else None
        completed_str = started_str if sd.get("status") == "completed" else None
        stages.append(
            StageInfoResponse(
                name=stage_cfg,
                started_at=started_str if sd.get("status") in ("running", "completed", "waiting") else None,
                completed_at=completed_str,
                duration_ms=None,
                status=sd.get("status", "pending"),
            )
        )
    
    # Build persona response from tone data
    persona = None
    if tone:
        persona = PersonaResponse(
            name=tone.get("name") or state.get("target_name"),
            company=state.get("company"),
            role=state.get("role"),
            industry=state.get("industry"),
            seniority=tone.get("seniority"),
            communication_style=tone.get("communication_style"),
            formality_level=tone.get("formality_level"),
            tone_keywords=tone.get("tone_keywords", []),
            language_hints=tone.get("language_hints"),
            key_interests=tone.get("interests", []),
            recommended_approach=tone.get("recommended_approach"),
        )
    
    return CampaignResponse(
        campaign_id=campaign_id,
        session_id=campaign.get("session_id"),
        status=campaign["status"],
        current_stage=campaign["current_stage"],
        target_company=state.get("company"),
        target_role=state.get("role"),
        drafts=drafts,
        llm_actions=llm_actions,
        stages=stages,
        persona=persona,
        error=campaign.get("error")
    )


# ═══════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Quick health check."""
    return {"status": "ok", "service": "Outreach Engine API"}


@app.get("/api/v1/health")
async def health_check():
    """
    Comprehensive health check including Ollama status.
    Returns detailed info about LLM connectivity and configuration.
    """
    ollama_status = await check_ollama_health()
    model_info = get_model_info()
    
    return {
        "status": "healthy" if ollama_status["connected"] else "degraded",
        "service": "Outreach Engine API",
        "ollama": {
            "connected": ollama_status["connected"],
            "base_url": ollama_status["base_url"],
            "configured_model": ollama_status["model"],
            "available_models": ollama_status.get("available_models", []),
            "error": ollama_status.get("error")
        },
        "model_config": model_info,
        "features": {
            "document_ingestion": True,
            "multi_channel_drafts": True,
            "persona_analysis": True,
            "llm_actions_tracking": True
        }
    }


@app.get("/api/v1/models")
async def get_recommended_models():
    """Get list of recommended Ollama models with specs."""
    models = list_recommended_models()
    return {
        "recommended": models,
        "note": "Pull with: ollama pull <model_name>"
    }


@app.post("/api/v1/campaigns", response_model=CampaignResponse)
async def create_campaign(
    request: CampaignStartRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new outreach campaign.
    
    Accepts:
    - URL (LinkedIn, company website, etc.)
    - Plain text (profile description)
    - File path (PDF/DOC with mock data)
    """
    try:
        # Create campaign (with optional session_id)
        campaign_id = state_manager.create_campaign(
            input_data={
                "type": request.input_type,
                "content": request.content
            },
            session_id=request.session_id
        )
        
        # Start workflow in background
        background_tasks.add_task(
            run_campaign_workflow,
            campaign_id,
            request.content
        )
        
        campaign = state_manager.get_campaign(campaign_id)
        return _build_campaign_response(campaign, campaign_id)
        
    except Exception as exc:
        logger.error(f"Failed to create campaign: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/campaigns/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str | None = None,
    background_tasks: BackgroundTasks = None
):
    """
    Upload a PDF or DOC file and start a campaign.
    Accepts an optional session_id query parameter.
    """
    try:
        # Validate file type
        if not file.filename.endswith(('.pdf', '.docx', '.doc')):
            raise HTTPException(
                status_code=400,
                detail="Only PDF and DOC/DOCX files are supported"
            )
        
        # Save file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Uploaded file: {file_path}")
        
        # Create campaign with file path (use existing session if provided)
        campaign_id = state_manager.create_campaign(
            input_data={
                "type": "file",
                "content": str(file_path)
            },
            session_id=session_id
        )
        
        # Start workflow in background
        background_tasks.add_task(
            run_campaign_workflow,
            campaign_id,
            str(file_path)
        )
        
        campaign = state_manager.get_campaign(campaign_id)
        return _build_campaign_response(campaign, campaign_id)
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"File upload failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str):
    """Get campaign status and results including LLM actions."""
    campaign = state_manager.get_campaign(campaign_id)
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return _build_campaign_response(campaign, campaign_id)


@app.get("/api/v1/campaigns/{campaign_id}/stream")
async def stream_campaign_updates(campaign_id: str):
    """
    Server-Sent Events endpoint for real-time campaign updates.
    """
    campaign = state_manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    async def event_generator():
        # Subscribe to campaign events
        queue = state_manager.subscribe(campaign_id)
        
        try:
            # Send current state first
            yield f"data: {campaign}\n\n"
            
            # Stream updates
            while True:
                event = await queue.get()
                yield f"data: {event}\n\n"
                
                # End stream if campaign completed or failed
                if event.get("type") == "stage_update":
                    if event.get("status") in ("completed", "failed"):
                        current_campaign = state_manager.get_campaign(campaign_id)
                        if current_campaign and current_campaign.get("status") in ("completed", "failed"):
                            break
        finally:
            state_manager.unsubscribe(campaign_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


class ApprovalRequest(BaseModel):
    """Request body for draft approvals."""
    approved: list[str] = []
    regen: list[str] = []
    skipped: list[str] = []


@app.post("/api/v1/campaigns/{campaign_id}/approve")
async def approve_drafts(
    campaign_id: str,
    request: ApprovalRequest,
    background_tasks: BackgroundTasks
):
    """
    Handle draft approval/regeneration.
    User selects which channels to approve or regenerate.
    """
    campaign = state_manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Update state with user choices
    state = campaign.get("state", {})
    state["approved_channels"] = request.approved
    state["regen_channels"] = request.regen
    state["__resume__"] = {"approved": request.approved, "regen": request.regen}
    
    state_manager.update_state(campaign_id, state)
    
    logger.info(f"Approval received for campaign {campaign_id}: approved={request.approved}, regen={request.regen}")
    
    # Resume workflow from interrupt
    background_tasks.add_task(
        run_campaign_workflow,
        campaign_id,
        state.get("raw_input", ""),
        resume_from_interrupt=True
    )
    
    return {"status": "ok", "approved": request.approved, "regen": request.regen}


# ═══════════════════════════════════════════════════════════════════════════
# SESSION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/sessions", response_model=list[SessionSummary])
async def list_sessions():
    """Get all sessions with summaries for the sidebar."""
    sessions = state_manager.list_sessions()
    return [
        SessionSummary(
            session_id=s["session_id"],
            name=s["name"],
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            campaign_count=s["campaign_count"],
            last_company=s.get("last_company"),
            last_role=s.get("last_role")
        )
        for s in sessions
    ]


@app.post("/api/v1/sessions", response_model=SessionSummary)
async def create_session(request: SessionCreateRequest = None):
    """Create a new empty session."""
    name = request.name if request else None
    session_id = state_manager.create_session(name)
    session = state_manager.get_session(session_id)
    
    return SessionSummary(
        session_id=session["session_id"],
        name=session["name"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        campaign_count=0,
        last_company=None,
        last_role=None
    )


@app.get("/api/v1/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str):
    """Get full session details with all campaigns."""
    session = state_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    campaigns = [
        _build_campaign_response(c, c["id"]) 
        for c in session.get("campaigns", [])
    ]
    
    return SessionDetail(
        session_id=session["session_id"],
        name=session["name"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        campaigns=campaigns
    )


@app.delete("/api/v1/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its campaigns."""
    if not state_manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"status": "ok", "deleted": session_id}


@app.put("/api/v1/sessions/{session_id}")
async def update_session_name(session_id: str, name: str):
    """Update session name."""
    session = state_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session["name"] = name
    state_manager._save_session(session_id)
    
    return {"status": "ok", "name": name}


# ═══════════════════════════════════════════════════════════════════════════
# STATIC FILES (for serving frontend in production)
# ═══════════════════════════════════════════════════════════════════════════

# Uncomment when frontend is built
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
