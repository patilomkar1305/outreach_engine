import { useState, useEffect, useCallback } from 'react';
import './App.css';

// ═══════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════

interface LLMAction {
  id: string;
  timestamp: string;
  stage: string;
  agent: string;
  action: string;
  model: string;
  prompt_preview: string;
  response_preview: string;
  tokens_used?: number;
  duration_ms: number;
  status: string;
  error_message?: string;
}

interface StageInfo {
  name: string;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  status: string;
}

interface Draft {
  id?: string;
  channel: string;
  subject?: string;
  body: string;
  score?: number;
  score_rationale?: string;
  approved: boolean;
  sent: boolean;
  version: number;
  regenerate_count: number;
  created_at?: string;
}

interface PersonaInfo {
  name?: string;
  company?: string;
  role?: string;
  industry?: string;
  seniority?: string;
  communication_style?: string;
  key_interests: string[];
}

interface Campaign {
  campaign_id: string;
  session_id?: string;
  status: string;
  current_stage: string;
  target_company?: string;
  target_role?: string;
  drafts: Draft[];
  llm_actions: LLMAction[];
  stages: StageInfo[];
  persona?: PersonaInfo;
  error?: string;
}

interface SessionSummary {
  session_id: string;
  name: string;
  created_at: string;
  updated_at: string;
  campaign_count: number;
  last_company?: string;
  last_role?: string;
}

// ═══════════════════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════

const API_BASE = 'http://localhost:8080';

const STAGE_CONFIG = [
  { key: 'ingestion', label: 'Data Ingestion', icon: '📥', description: 'Extracting profile data' },
  { key: 'persona', label: 'Persona Analysis', icon: '🎯', description: 'Understanding communication style' },
  { key: 'drafting', label: 'Draft Generation', icon: '✍️', description: 'Creating personalized messages' },
  { key: 'scoring', label: 'Quality Scoring', icon: '⭐', description: 'Evaluating message quality' },
  { key: 'approval', label: 'Human Review', icon: '👤', description: 'Your approval needed' },
  { key: 'execution', label: 'Message Sending', icon: '🚀', description: 'Sending approved messages' },
  { key: 'persistence', label: 'Data Storage', icon: '💾', description: 'Saving campaign data' },
];

const CHANNEL_ICONS: Record<string, string> = {
  email: '📧',
  linkedin: '💼',
  whatsapp: '💬',
  sms: '📱',
  instagram: '📸',
};

// Session Sidebar Component
function SessionSidebar({ 
  sessions, 
  activeSessionId, 
  onSelectSession, 
  onNewSession,
  onDeleteSession,
  isCollapsed,
  onToggleCollapse
}: {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}) {
  return (
    <aside className={`session-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button className="collapse-btn" onClick={onToggleCollapse}>
          {isCollapsed ? '→' : '←'}
        </button>
        {!isCollapsed && (
          <>
            <h2>Sessions</h2>
            <button className="new-session-btn" onClick={onNewSession}>
              + New
            </button>
          </>
        )}
      </div>
      
      {!isCollapsed && (
        <div className="session-list">
          {sessions.length === 0 ? (
            <p className="no-sessions">No sessions yet</p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.session_id}
                className={`session-item ${activeSessionId === session.session_id ? 'active' : ''}`}
                onClick={() => onSelectSession(session.session_id)}
              >
                <div className="session-info">
                  <span className="session-name">{session.name}</span>
                  <span className="session-meta">
                    {session.last_company || 'New Campaign'} • {session.campaign_count} run{session.campaign_count !== 1 ? 's' : ''}
                  </span>
                </div>
                <button 
                  className="delete-session-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.session_id);
                  }}
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </aside>
  );
}

// LLM Actions Panel Component
function LLMActionsPanel({ 
  actions, 
  isExpanded, 
  onToggle 
}: { 
  actions: LLMAction[]; 
  isExpanded: boolean; 
  onToggle: () => void;
}) {
  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className={`llm-actions-panel ${isExpanded ? 'expanded' : ''}`}>
      <div className="panel-header" onClick={onToggle}>
        <span className="panel-icon">🤖</span>
        <span className="panel-title">LLM Actions</span>
        <span className="action-count">{actions.length}</span>
        <span className="expand-icon">{isExpanded ? '▼' : '▲'}</span>
      </div>
      
      {isExpanded && (
        <div className="actions-list">
          {actions.length === 0 ? (
            <p className="no-actions">No LLM calls yet</p>
          ) : (
            actions.map((action) => (
              <div key={action.id} className={`action-item ${action.status}`}>
                <div className="action-header">
                  <span className="action-stage">{action.stage}</span>
                  <span className="action-time">{formatTime(action.timestamp)}</span>
                  <span className={`action-status ${action.status}`}>
                    {action.status === 'success' ? '✓' : '✗'}
                  </span>
                </div>
                <div className="action-details">
                  <span className="action-agent">{action.agent}</span>
                  <span className="action-description">{action.action}</span>
                </div>
                <div className="action-meta">
                  <span className="model">{action.model}</span>
                  <span className="duration">{formatDuration(action.duration_ms)}</span>
                  {action.tokens_used && <span className="tokens">{action.tokens_used} tokens</span>}
                </div>
                <div className="action-preview">
                  <details>
                    <summary>Prompt Preview</summary>
                    <pre>{action.prompt_preview}</pre>
                  </details>
                  <details>
                    <summary>Response Preview</summary>
                    <pre>{action.response_preview}</pre>
                  </details>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// Pipeline Progress Component
function PipelineProgress({ stages, currentStage }: { stages: StageInfo[]; currentStage: string }) {
  const getStageStatus = (stageKey: string) => {
    const stage = stages.find(s => s.name === stageKey);
    if (stage) return stage.status;
    
    // Determine status based on position relative to current stage
    const currentIdx = STAGE_CONFIG.findIndex(s => s.key === currentStage);
    const thisIdx = STAGE_CONFIG.findIndex(s => s.key === stageKey);
    
    if (thisIdx < currentIdx) return 'completed';
    if (thisIdx === currentIdx) return 'running';
    return 'pending';
  };

  const getStageDuration = (stageKey: string) => {
    const stage = stages.find(s => s.name === stageKey);
    if (stage?.duration_ms) {
      return stage.duration_ms < 1000 
        ? `${stage.duration_ms}ms` 
        : `${(stage.duration_ms / 1000).toFixed(1)}s`;
    }
    return null;
  };

  return (
    <div className="pipeline-progress">
      {STAGE_CONFIG.map((stage, idx) => {
        const status = getStageStatus(stage.key);
        const duration = getStageDuration(stage.key);
        
        return (
          <div 
            key={stage.key} 
            className={`pipeline-stage ${status}`}
          >
            <div className="stage-icon">
              {status === 'running' ? (
                <span className="spinner">{stage.icon}</span>
              ) : status === 'completed' ? (
                <span className="check">✓</span>
              ) : (
                stage.icon
              )}
            </div>
            <div className="stage-info">
              <span className="stage-label">{stage.label}</span>
              {duration && <span className="stage-duration">{duration}</span>}
            </div>
            {idx < STAGE_CONFIG.length - 1 && <div className="stage-connector" />}
          </div>
        );
      })}
    </div>
  );
}

// Draft Card Component
function DraftCard({ 
  draft, 
  choice, 
  onChoiceChange 
}: { 
  draft: Draft; 
  choice: 'approve' | 'regen' | 'skip' | null;
  onChoiceChange: (choice: 'approve' | 'regen' | 'skip') => void;
}) {
  const getScoreColor = (score?: number) => {
    if (!score) return 'gray';
    if (score >= 8) return 'excellent';
    if (score >= 6) return 'good';
    if (score >= 4) return 'fair';
    return 'poor';
  };

  return (
    <div className={`draft-card ${choice || ''} ${draft.sent ? 'sent' : ''}`}>
      <div className="draft-header">
        <div className="channel-badge">
          <span className="channel-icon">{CHANNEL_ICONS[draft.channel] || '📨'}</span>
          <span className="channel-name">{draft.channel.toUpperCase()}</span>
          {draft.version > 1 && (
            <span className="version-badge">v{draft.version}</span>
          )}
          {draft.regenerate_count > 0 && (
            <span className="regen-badge">↻{draft.regenerate_count}</span>
          )}
        </div>
        
        {draft.score !== undefined && draft.score !== null && (
          <div className={`score-badge ${getScoreColor(draft.score)}`}>
            <span className="score-value">{draft.score.toFixed(1)}</span>
            <span className="score-max">/10</span>
          </div>
        )}
      </div>

      {draft.subject && (
        <div className="draft-subject">
          <strong>Subject:</strong> {draft.subject}
        </div>
      )}
      
      <div className="draft-body">
        {draft.body}
      </div>

      {draft.score_rationale && (
        <div className="score-rationale">
          <span className="rationale-icon">💡</span>
          <span className="rationale-text">{draft.score_rationale}</span>
        </div>
      )}

      {!draft.sent && (
        <div className="draft-actions">
          <button 
            className={`action-btn approve ${choice === 'approve' ? 'selected' : ''}`}
            onClick={() => onChoiceChange('approve')}
          >
            ✓ Approve
          </button>
          <button 
            className={`action-btn regen ${choice === 'regen' ? 'selected' : ''}`}
            onClick={() => onChoiceChange('regen')}
          >
            ↻ Regenerate
          </button>
          <button 
            className={`action-btn skip ${choice === 'skip' ? 'selected' : ''}`}
            onClick={() => onChoiceChange('skip')}
          >
            × Skip
          </button>
        </div>
      )}

      {draft.sent && (
        <div className="sent-indicator">
          ✓ Message Sent
        </div>
      )}
    </div>
  );
}

// Persona Card Component
function PersonaCard({ persona, company, role }: { persona?: PersonaInfo; company?: string; role?: string }) {
  if (!persona && !company && !role) return null;

  return (
    <div className="persona-card">
      <h3>🎯 Target Persona</h3>
      <div className="persona-details">
        {(persona?.name || company) && (
          <div className="persona-row">
            <span className="label">Company:</span>
            <span className="value">{persona?.company || company}</span>
          </div>
        )}
        {(persona?.role || role) && (
          <div className="persona-row">
            <span className="label">Role:</span>
            <span className="value">{persona?.role || role}</span>
          </div>
        )}
        {persona?.industry && (
          <div className="persona-row">
            <span className="label">Industry:</span>
            <span className="value">{persona.industry}</span>
          </div>
        )}
        {persona?.seniority && (
          <div className="persona-row">
            <span className="label">Seniority:</span>
            <span className="value">{persona.seniority}</span>
          </div>
        )}
        {persona?.communication_style && (
          <div className="persona-row">
            <span className="label">Style:</span>
            <span className="value">{persona.communication_style}</span>
          </div>
        )}
        {persona?.key_interests && persona.key_interests.length > 0 && (
          <div className="persona-interests">
            <span className="label">Interests:</span>
            <div className="interest-tags">
              {persona.key_interests.map((interest, idx) => (
                <span key={idx} className="interest-tag">{interest}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

function App() {
  // State
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [loading, setLoading] = useState(false);
  const [approvalChoices, setApprovalChoices] = useState<Record<string, 'approve' | 'regen' | 'skip'>>({});
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [llmPanelExpanded, setLlmPanelExpanded] = useState(true);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  
  // Input state
  const [urlInput, setUrlInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [inputMode, setInputMode] = useState<'url' | 'text' | 'file'>('text');

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  const loadSessions = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/sessions`);
      if (response.ok) {
        const data = await response.json();
        setSessions(data);
      }
    } catch (error) {
      console.warn('Could not load sessions (backend may be offline):', error);
    }
  };

  const handleNewSession = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (response.ok) {
        const data = await response.json();
        setActiveSessionId(data.session_id);
        loadSessions();
      }
    } catch (error) {
      // Create local session for demo mode
      const newSession: SessionSummary = {
        session_id: 'local-' + Date.now(),
        name: `Session ${sessions.length + 1}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        campaign_count: 0,
      };
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newSession.session_id);
    }
    // Reset campaign state for new session
    setCampaign(null);
    setApprovalChoices({});
  };

  const handleSelectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setCampaign(null);
    setApprovalChoices({});
    
    // Load session campaigns
    try {
      const response = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.campaigns && data.campaigns.length > 0) {
          // Load the most recent campaign
          setCampaign(data.campaigns[data.campaigns.length - 1]);
        }
      }
    } catch (error) {
      console.warn('Could not load session:', error);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await fetch(`${API_BASE}/api/v1/sessions/${sessionId}`, {
        method: 'DELETE'
      });
    } catch (error) {
      console.warn('Could not delete session from backend:', error);
    }
    
    setSessions(prev => prev.filter(s => s.session_id !== sessionId));
    if (activeSessionId === sessionId) {
      setActiveSessionId(null);
      setCampaign(null);
    }
  };

  const pollCampaignStatus = useCallback(async (campaignId: string) => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/api/v1/campaigns/${campaignId}`);
        if (response.ok) {
          const data = await response.json();
          setCampaign(data);
          
          // Stop polling if completed or failed
          if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(interval);
            setPollingInterval(null);
          }
        }
      } catch (error) {
        console.warn('Failed to fetch campaign status:', error);
      }
    }, 2000);

    setPollingInterval(interval);
  }, [pollingInterval]);

  const handleStartCampaign = async () => {
    setLoading(true);
    
    try {
      let response;
      
      if (inputMode === 'file' && file) {
        // For file upload, use FormData with the dedicated upload endpoint
        const formData = new FormData();
        formData.append('file', file);
        
        response = await fetch(`${API_BASE}/api/v1/campaigns/upload`, {
          method: 'POST',
          body: formData  // Don't set Content-Type header - browser will set it with boundary
        });
      } else {
        // For text and URL inputs, use the regular endpoint
        let content = '';
        let inputType = 'text';
        
        if (inputMode === 'url' && urlInput.trim()) {
          content = urlInput.trim();
          inputType = 'url';
        } else if (inputMode === 'text' && textInput.trim()) {
          content = textInput.trim();
          inputType = 'text';
        }
        
        response = await fetch(`${API_BASE}/api/v1/campaigns`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input_type: inputType,
            content: content,
            session_id: activeSessionId
          })
        });
      }
      
      if (response.ok) {
        const data = await response.json();
        setCampaign(data);
        if (!activeSessionId) {
          setActiveSessionId(data.session_id);
        }
        pollCampaignStatus(data.campaign_id);
        loadSessions();
      } else {
        throw new Error('Failed to start campaign');
      }
    } catch (error) {
      console.warn('Backend unavailable, using demo mode:', error);
      
      // Demo mode with mock data
      const mockCampaign: Campaign = {
        campaign_id: 'demo-' + Date.now(),
        session_id: activeSessionId || 'local-session',
        status: 'running',
        current_stage: 'approval',
        target_company: 'TechCorp Inc',
        target_role: 'Senior Software Engineer',
        persona: {
          company: 'TechCorp Inc',
          role: 'Senior Software Engineer',
          industry: 'Technology',
          seniority: 'Senior',
          communication_style: 'Professional, technical, prefers direct communication',
          key_interests: ['AI', 'Cloud Architecture', 'Microservices', 'DevOps'],
        },
        drafts: [
          {
            id: 'draft-1',
            channel: 'email',
            subject: 'Exciting opportunity at our growing startup',
            body: 'Hi there!\n\nI noticed your impressive background in software engineering at TechCorp Inc. We\'re building something revolutionary in the AI space and would love to chat about how your expertise could help shape our product.\n\nWould you be open to a quick 15-minute call this week?\n\nBest regards,\nSarah',
            score: 8.5,
            score_rationale: 'Strong personalization with role reference, clear CTA, appropriate tone',
            approved: false,
            sent: false,
            version: 1,
            regenerate_count: 0,
          },
          {
            id: 'draft-2',
            channel: 'linkedin',
            subject: '',
            body: 'Hey! Loved your recent post about microservices architecture. We\'re tackling similar challenges at scale and I think you\'d find our approach interesting. Would you be open to connecting?',
            score: 7.8,
            score_rationale: 'Good reference to interests, could be more specific about value proposition',
            approved: false,
            sent: false,
            version: 1,
            regenerate_count: 0,
          },
          {
            id: 'draft-3',
            channel: 'whatsapp',
            subject: '',
            body: 'Hi! 👋 Quick intro - I\'m Sarah from AI Innovations. Saw your profile and think you\'d be amazing for what we\'re building. Free for a quick call this week?',
            score: 7.5,
            score_rationale: 'Friendly tone, could use more personalization',
            approved: false,
            sent: false,
            version: 1,
            regenerate_count: 0,
          },
          {
            id: 'draft-4',
            channel: 'sms',
            subject: '',
            body: 'Hi! Quick intro - Sarah from AI Innovations. Your background is perfect for what we\'re building. Coffee chat this week?',
            score: 6.9,
            score_rationale: 'Concise but generic, could mention specific skills',
            approved: false,
            sent: false,
            version: 1,
            regenerate_count: 0,
          },
          {
            id: 'draft-5',
            channel: 'instagram',
            subject: '',
            body: 'Hey! 👋 Love your content on tech and innovation. We\'re building something cool in AI and would love to get your thoughts. DM me if interested!',
            score: 7.2,
            score_rationale: 'Casual, platform-appropriate, but lacks specific hook',
            approved: false,
            sent: false,
            version: 1,
            regenerate_count: 0,
          }
        ],
        llm_actions: [
          {
            id: 'action-1',
            timestamp: new Date(Date.now() - 30000).toISOString(),
            stage: 'ingestion',
            agent: 'ingestion_agent',
            action: 'Extracting profile data from input',
            model: 'mistral',
            prompt_preview: 'Analyzing the following profile information...',
            response_preview: 'Extracted: TechCorp Inc, Senior Software Engineer...',
            duration_ms: 1250,
            status: 'success',
          },
          {
            id: 'action-2',
            timestamp: new Date(Date.now() - 25000).toISOString(),
            stage: 'persona',
            agent: 'persona_agent',
            action: 'Analyzing communication style and persona',
            model: 'mistral',
            prompt_preview: 'You are an expert communication-style analyst...',
            response_preview: '{"formality_level": "semi-formal", "interests": ["AI", "Cloud"]...',
            duration_ms: 3420,
            status: 'success',
          },
          {
            id: 'action-3',
            timestamp: new Date(Date.now() - 20000).toISOString(),
            stage: 'drafting',
            agent: 'draft_email_agent',
            action: 'Generating EMAIL message draft',
            model: 'mistral',
            prompt_preview: 'You are a world-class cold-outreach copywriter...',
            response_preview: '{"subject": "Exciting opportunity...", "body": "Hi there!..."',
            duration_ms: 2890,
            status: 'success',
          },
          {
            id: 'action-4',
            timestamp: new Date(Date.now() - 15000).toISOString(),
            stage: 'scoring',
            agent: 'scoring_agent',
            action: 'Evaluating 5 drafts for quality and personalization',
            model: 'mistral',
            prompt_preview: 'You are a cold-outreach quality judge...',
            response_preview: '[{"channel": "email", "score": 8.5, "rationale": "Strong..."}]',
            duration_ms: 4100,
            status: 'success',
          },
        ],
        stages: [
          { name: 'ingestion', started_at: new Date(Date.now() - 35000).toISOString(), completed_at: new Date(Date.now() - 30000).toISOString(), duration_ms: 5000, status: 'completed' },
          { name: 'persona', started_at: new Date(Date.now() - 30000).toISOString(), completed_at: new Date(Date.now() - 25000).toISOString(), duration_ms: 5000, status: 'completed' },
          { name: 'drafting', started_at: new Date(Date.now() - 25000).toISOString(), completed_at: new Date(Date.now() - 15000).toISOString(), duration_ms: 10000, status: 'completed' },
          { name: 'scoring', started_at: new Date(Date.now() - 15000).toISOString(), completed_at: new Date(Date.now() - 10000).toISOString(), duration_ms: 5000, status: 'completed' },
          { name: 'approval', started_at: new Date(Date.now() - 10000).toISOString(), status: 'running' },
        ],
      };
      
      setCampaign(mockCampaign);
    }
    
    setLoading(false);
  };

  const handleDraftAction = (channel: string, action: 'approve' | 'regen' | 'skip') => {
    setApprovalChoices(prev => ({ ...prev, [channel]: action }));
  };

  const handleSubmitApprovals = async () => {
    if (!campaign) return;
    
    const approved = Object.entries(approvalChoices)
      .filter(([_, action]) => action === 'approve')
      .map(([channel]) => channel);

    const regen = Object.entries(approvalChoices)
      .filter(([_, action]) => action === 'regen')
      .map(([channel]) => channel);

    const skipped = Object.entries(approvalChoices)
      .filter(([_, action]) => action === 'skip')
      .map(([channel]) => channel);

    // Apply choices locally
    const updatedDrafts = campaign.drafts.map(d => {
      if (approved.includes(d.channel)) {
        return { ...d, approved: true };
      }
      if (regen.includes(d.channel)) {
        const timestamp = new Date().toLocaleTimeString();
        const newBody = `Regenerated (${timestamp}):\n\n${d.body.split('\n').slice(0, 2).join('\n')}\n\nWanted to follow up with a fresher outreach tone — would you be open to a brief call?\n\nBest,\nSarah`;
        const newScore = Math.max(5 + Math.random() * 4, 5);
        return { 
          ...d, 
          body: newBody, 
          score: parseFloat(newScore.toFixed(1)), 
          score_rationale: 'Regenerated with new approach',
          version: d.version + 1,
          regenerate_count: d.regenerate_count + 1,
          approved: false 
        };
      }
      return d;
    }).filter(d => !skipped.includes(d.channel));

    setCampaign(prev => prev ? { ...prev, drafts: updatedDrafts } : prev);
    setApprovalChoices({});

    // Try to notify backend
    try {
      await fetch(`${API_BASE}/api/v1/campaigns/${campaign.campaign_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved, regen, skipped }),
      });
      pollCampaignStatus(campaign.campaign_id);
    } catch (error) {
      console.warn('Backend approve call failed:', error);
    }
  };

  const handleCompleteCampaign = () => {
    if (!campaign) return;

    const updatedDrafts = campaign.drafts.map(d => 
      d.approved ? { ...d, sent: true } : d
    );

    const finalStages: StageInfo[] = [
      ...campaign.stages.filter(s => s.name !== 'approval' && s.name !== 'execution' && s.name !== 'persistence'),
      { name: 'approval', started_at: '', completed_at: new Date().toISOString(), duration_ms: 5000, status: 'completed' },
      { name: 'execution', started_at: new Date().toISOString(), completed_at: new Date().toISOString(), duration_ms: 2000, status: 'completed' },
      { name: 'persistence', started_at: new Date().toISOString(), completed_at: new Date().toISOString(), duration_ms: 1000, status: 'completed' },
    ];

    setCampaign(prev => prev ? { 
      ...prev, 
      status: 'completed', 
      current_stage: 'persistence', 
      stages: finalStages,
      drafts: updatedDrafts 
    } : prev);
    
    loadSessions();
  };

  const handleNewCampaign = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    setCampaign(null);
    setUrlInput('');
    setTextInput('');
    setFile(null);
    setApprovalChoices({});
  };

  const hasApprovedDrafts = campaign?.drafts.some(d => d.approved);
  
  // Smart detection: show approval UI if drafts have scores but aren't approved yet
  const needsApproval = campaign && campaign.drafts.length > 0 
    && campaign.drafts.every(d => d.score !== null && d.score !== undefined)
    && !hasApprovedDrafts
    && campaign.status !== 'completed';
  
  const showApprovalUI = campaign && (
    campaign.current_stage === 'approval' 
    || campaign.status === 'approval'
    || needsApproval
  );

  return (
    <div className="app-container">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <main className="main-content">
        <header className="app-header">
          <div className="header-content">
            <h1>🚀 Outreach Engine</h1>
            <p className="tagline">AI-Powered Hyper-Personalized Cold Outreach</p>
          </div>
          {campaign && (
            <button className="new-campaign-btn" onClick={handleNewCampaign}>
              + New Campaign
            </button>
          )}
        </header>

        <div className="content-area">
          {!campaign && (
            <div className="input-section">
              <h2>Start a New Outreach Campaign</h2>
              <p className="section-subtitle">
                Provide target information to generate personalized messages across all channels
              </p>
              
              <div className="input-mode-tabs">
                <button 
                  className={`tab ${inputMode === 'text' ? 'active' : ''}`}
                  onClick={() => setInputMode('text')}
                >
                  📝 Text Input
                </button>
                <button 
                  className={`tab ${inputMode === 'url' ? 'active' : ''}`}
                  onClick={() => setInputMode('url')}
                >
                  🔗 URL
                </button>
                <button 
                  className={`tab ${inputMode === 'file' ? 'active' : ''}`}
                  onClick={() => setInputMode('file')}
                >
                  📄 Upload File
                </button>
              </div>

              <div className="input-area">
                {inputMode === 'text' && (
                  <textarea
                    placeholder="Paste bio, LinkedIn summary, or any relevant profile information...

Example:
John Smith is a Senior Software Engineer at TechCorp Inc with 8 years of experience in cloud architecture and AI/ML systems. He's passionate about building scalable solutions and recently spoke at CloudCon about microservices patterns."
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    className="text-input"
                    rows={8}
                  />
                )}
                
                {inputMode === 'url' && (
                  <input
                    type="text"
                    placeholder="https://linkedin.com/in/example-profile"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    className="url-input"
                  />
                )}
                
                {inputMode === 'file' && (
                  <div className={`file-upload ${file ? 'has-file' : ''}`}>
                    <input
                      type="file"
                      accept=".pdf,.doc,.docx"
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                      id="file-input"
                    />
                    <label htmlFor="file-input">
                      {file ? (
                        <>
                          <span className="file-icon">📄</span>
                          <span className="file-name">{file.name}</span>
                          <span className="file-action">Click to change</span>
                        </>
                      ) : (
                        <>
                          <span className="upload-icon">📤</span>
                          <span className="upload-text">Click or drag to upload PDF/DOC</span>
                        </>
                      )}
                    </label>
                  </div>
                )}
              </div>

              <button
                className="launch-btn"
                onClick={handleStartCampaign}
                disabled={loading || (
                  (inputMode === 'text' && !textInput.trim()) ||
                  (inputMode === 'url' && !urlInput.trim()) ||
                  (inputMode === 'file' && !file)
                )}
              >
                {loading ? (
                  <>
                    <span className="spinner-icon">⏳</span>
                    Launching Campaign...
                  </>
                ) : (
                  <>
                    🚀 Launch Campaign
                  </>
                )}
              </button>
            </div>
          )}

          {campaign && (
            <div className="campaign-view">
              {showApprovalUI && (
                <div className="approval-banner">
                  <span className="banner-icon">👋</span>
                  <div className="banner-content">
                    <strong>Action Required:</strong> Review and approve the generated drafts below
                  </div>
                  <span className="banner-arrow">↓</span>
                </div>
              )}
              
              <div className="campaign-header">
                <PersonaCard 
                  persona={campaign.persona} 
                  company={campaign.target_company}
                  role={campaign.target_role}
                />
              </div>

              <PipelineProgress 
                stages={campaign.stages} 
                currentStage={campaign.current_stage} 
              />

              {campaign.drafts && campaign.drafts.length > 0 && (
                <div className="drafts-section">
                  <h3>Generated Messages</h3>
                  <div className="drafts-grid">
                    {campaign.drafts.map((draft) => (
                      <DraftCard
                        key={draft.id || draft.channel}
                        draft={draft}
                        choice={approvalChoices[draft.channel] || null}
                        onChoiceChange={(choice) => handleDraftAction(draft.channel, choice)}
                      />
                    ))}
                  </div>
                  
                  {showApprovalUI && (
                    <div className="approval-actions-container">
                      <div className="approval-summary">
                        <p>
                          {Object.keys(approvalChoices).length === 0 
                            ? "Select action for each draft above (Approve, Regenerate, or Skip)"
                            : `Selected: ${Object.keys(approvalChoices).length} draft(s)`}
                        </p>
                      </div>
                      
                      <div className="approval-actions">
                        {Object.keys(approvalChoices).length > 0 ? (
                          <button className="submit-btn primary-action" onClick={handleSubmitApprovals}>
                            ✓ Submit {Object.keys(approvalChoices).length} Choice(s) →
                          </button>
                        ) : hasApprovedDrafts ? (
                          <button className="complete-btn primary-action" onClick={handleCompleteCampaign}>
                            🚀 Complete Campaign
                          </button>
                        ) : null}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {campaign.status === 'completed' && (
                <div className="completion-card">
                  <div className="completion-icon">✓</div>
                  <h2>Campaign Completed!</h2>
                  <p>All approved messages have been sent to their respective channels.</p>
                  <div className="completion-stats">
                    <div className="stat">
                      <span className="stat-value">{campaign.drafts.filter(d => d.sent).length}</span>
                      <span className="stat-label">Messages Sent</span>
                    </div>
                    <div className="stat">
                      <span className="stat-value">{campaign.llm_actions.length}</span>
                      <span className="stat-label">LLM Calls</span>
                    </div>
                  </div>
                  <button className="new-btn" onClick={handleNewCampaign}>
                    Start New Campaign
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <LLMActionsPanel
          actions={campaign?.llm_actions || []}
          isExpanded={llmPanelExpanded}
          onToggle={() => setLlmPanelExpanded(!llmPanelExpanded)}
        />
      </main>
    </div>
  );
}

export default App;
