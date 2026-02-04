<div align="center">

# 🚀 Outreach Engine

### AI-Powered Hyper-Personalized Cold Outreach Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://reactjs.org/)
[![LangGraph](https://img.shields.io/badge/langgraph-0.2+-green.svg)](https://github.com/langchain-ai/langgraph)
[![Ollama](https://img.shields.io/badge/ollama-offline%20LLM-purple.svg)](https://ollama.ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Generate deeply personalized, multi-channel cold outreach messages using 100% offline LLM processing**

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API Reference](#-api-reference) • [Contributing](#-contributing)

---

</div>

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Usage Guide](#-usage-guide)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**Outreach Engine** is a fully offline, LLM-powered platform that generates hyper-personalized cold outreach messages across multiple channels. Unlike cloud-based solutions, all AI processing happens locally using Ollama, ensuring complete privacy and control over your data.

### Problem It Solves

Traditional cold outreach is:
- ❌ Generic and template-based
- ❌ Poorly personalized
- ❌ Mismatched in tone
- ❌ Dependent on cloud APIs (privacy concerns)

**Outreach Engine** provides:
- ✅ Deep personalization based on prospect data
- ✅ Tone-matched messaging (casual, professional, mixed)
- ✅ Multi-channel generation (Email, LinkedIn, WhatsApp, SMS, Instagram)
- ✅ 100% offline LLM processing
- ✅ Knowledge base for continuous improvement

---

## ✨ Features

### Core Features

| Feature | Description |
|---------|-------------|
| **🔒 Offline LLM** | All AI processing via Ollama (Mistral/LLaMA) - no external API calls |
| **📥 Multi-Source Ingestion** | LinkedIn URLs, raw text, PDF/DOC file uploads |
| **🎭 Persona Analysis** | Detects formality, tone, interests, communication style |
| **📝 5-Channel Drafts** | Email, LinkedIn DM, WhatsApp, SMS, Instagram DM |
| **⭐ Quality Scoring** | AI-powered 0-10 scoring with detailed rationale |
| **👤 Human-in-the-Loop** | Approve, regenerate, or skip each draft |
| **💾 Knowledge Base** | ChromaDB stores personas for future reference |
| **🔄 Similarity Matching** | Leverages past outreach for similar prospects |

### Stretch Features

| Feature | Description |
|---------|-------------|
| **📊 Score Analytics** | Visual scoring breakdown per channel |
| **🔄 Regeneration** | One-click regenerate with improved prompts |
| **📱 Responsive UI** | Works on desktop and tablet |
| **🐳 Docker Ready** | One-command deployment with Docker Compose |

---

## 🛠 Tech Stack

### Backend

| Technology | Purpose |
|------------|---------|
| **Python 3.10+** | Core runtime |
| **FastAPI** | REST API framework |
| **LangGraph** | Workflow orchestration (7-stage pipeline) |
| **LangChain** | LLM integration & tools |
| **Ollama** | Local LLM inference (Mistral) |
| **ChromaDB** | Vector storage for personas |
| **PostgreSQL + pgvector** | Relational storage with embeddings |
| **sentence-transformers** | Offline embedding generation |

### Frontend

| Technology | Purpose |
|------------|---------|
| **React 18** | UI framework |
| **TypeScript** | Type safety |
| **Vite** | Build tool & dev server |
| **CSS3** | Styling (no external frameworks) |

### Infrastructure

| Technology | Purpose |
|------------|---------|
| **Docker** | Containerization |
| **Docker Compose** | Multi-service orchestration |
| **Uvicorn** | ASGI server |

---

## 🏗 Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │  URL Input  │ │ Text Input  │ │ File Upload │              │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│         └───────────────┼───────────────┘                      │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Campaign Progress Dashboard                 │   │
│  │  [Ingestion] → [Persona] → [Drafts] → [Score] → [Send]  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │     Draft Cards (Email, LinkedIn, WhatsApp, SMS, IG)    │   │
│  │         [Approve] [Regenerate] [Skip] per card          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST API (Port 8080)
┌─────────────────────────▼───────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  POST /api/v1/campaigns          → Start campaign        │  │
│  │  POST /api/v1/campaigns/upload   → File upload           │  │
│  │  GET  /api/v1/campaigns/{id}     → Get status & drafts   │  │
│  │  POST /api/v1/campaigns/{id}/approve → Submit decisions  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                   LANGGRAPH WORKFLOW                            │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌────────────────────────┐    │
│  │ Ingest   │───▶│ Persona  │───▶│    Parallel Drafts     │    │
│  │  Node    │    │ Analysis │    │ ┌────┐┌────┐┌────┐     │    │
│  └──────────┘    └──────────┘    │ │Mail││ LI ││ WA │     │    │
│                                   │ └────┘└────┘└────┘     │    │
│                                   │ ┌────┐┌────┐          │    │
│                                   │ │SMS ││ IG │          │    │
│                                   │ └────┘└────┘          │    │
│                                   └───────────┬───────────┘    │
│                                               ▼                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐      │
│  │ Persist  │◀───│ Execute  │◀───│   Score & Approve    │      │
│  │  Node    │    │  Node    │    │   (Human-in-Loop)    │      │
│  └──────────┘    └──────────┘    └──────────────────────┘      │
│                                           ▲    │                │
│                                           └────┘ (regenerate)   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                        STORAGE                                   │
│  ┌─────────────────┐         ┌─────────────────┐               │
│  │   PostgreSQL    │         │    ChromaDB     │               │
│  │  + pgvector     │         │  (Embeddings)   │               │
│  │                 │         │                 │               │
│  │ • profiles      │         │ • persona       │               │
│  │ • personas      │         │   vectors       │               │
│  │ • drafts        │         │ • similarity    │               │
│  │ • campaign_runs │         │   search        │               │
│  └─────────────────┘         └─────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                     OLLAMA (Local LLM)                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Model: Mistral 7B (or configurable)                    │   │
│  │  Endpoint: http://localhost:11434                       │   │
│  │  100% Offline - No external API calls                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Workflow Stages

| Stage | Node | Description |
|-------|------|-------------|
| 1 | **Ingestion** | Fetch URL, parse text, extract PDF/DOC content |
| 2 | **Persona Analysis** | Analyze tone, formality, interests using LLM |
| 3 | **Draft Generation** | Parallel generation of 5 channel-specific messages |
| 4 | **Scoring** | Quality scoring (0-10) with rationale |
| 5 | **Approval** | Human review: approve, regenerate, or skip |
| 6 | **Execution** | Send via Gmail/Twilio (or mock for demo) |
| 7 | **Persistence** | Store sanitized data to Postgres + ChromaDB |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** - [Download](https://nodejs.org/)
- **Ollama** - [Download](https://ollama.ai/download)
- **Docker** (optional) - [Download](https://www.docker.com/products/docker-desktop)

### Option 1: Quick Setup (Recommended)

```powershell
# Clone repository
git clone https://github.com/yourusername/outreach_engine.git
cd outreach_engine

# Run setup script
.\setup.ps1
```

### Option 2: Manual Setup

#### Step 1: Install Ollama & Pull Model

```powershell
# After installing Ollama from https://ollama.ai
ollama pull mistral

# Verify installation
ollama list
```

#### Step 2: Setup Python Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

#### Step 3: Setup Frontend

```powershell
cd frontend
npm install
cd ..
```

#### Step 4: Configure Environment

```powershell
# Copy example env file
copy .env.example .env

# Edit .env with your settings (see Configuration section)
```

#### Step 5: Start Services

```powershell
# Terminal 1: Start Ollama (if not running as service)
ollama serve

# Terminal 2: Start PostgreSQL (with Docker)
docker-compose up -d postgres

# Terminal 3: Start Backend API
.\venv\Scripts\Activate.ps1
python -m uvicorn app.api.main:app --reload --port 8080

# Terminal 4: Start Frontend
cd frontend
npm run dev
```

#### Step 6: Open Application

Navigate to **http://localhost:5173** in your browser.

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```ini
# ============================================
# OLLAMA (Required)
# ============================================
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# ============================================
# DATABASE (Required for persistence)
# ============================================
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=outreach_engine
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_data

# ============================================
# API
# ============================================
API_HOST=0.0.0.0
API_PORT=8080
DEBUG=true

# ============================================
# EMBEDDINGS (Offline)
# ============================================
EMBEDDING_MODEL=all-MiniLM-L6-v2

# ============================================
# EMAIL - Gmail OAuth (Optional)
# ============================================
GMAIL_CREDENTIALS_FILE=./credentials/gmail_credentials.json
GMAIL_TOKEN_FILE=./credentials/gmail_token.json

# ============================================
# SMS - Twilio (Optional)
# ============================================
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

### Supported LLM Models

| Model | Command | Size | Notes |
|-------|---------|------|-------|
| **Mistral** (default) | `ollama pull mistral` | 4.1GB | Best balance of speed/quality |
| **LLaMA 2** | `ollama pull llama2` | 3.8GB | Good general purpose |
| **Gemma** | `ollama pull gemma` | 5.0GB | Google's model |
| **Phi-2** | `ollama pull phi` | 1.7GB | Fastest, smaller output |

Change model in `.env`:
```ini
OLLAMA_MODEL=llama2
```

---

## 📖 Usage Guide

### Basic Workflow

1. **Enter Target Data**
   - Paste LinkedIn URL, OR
   - Enter raw profile text, OR
   - Upload PDF/DOC resume

2. **Launch Campaign**
   - Click "Launch Campaign" button
   - Watch real-time progress through 7 stages

3. **Review Drafts**
   - See all 5 channel drafts side-by-side
   - Each draft shows quality score (0-10)

4. **Make Decisions**
   - ✅ **Approve** - Mark for sending
   - 🔄 **Regenerate** - Generate new version
   - ❌ **Skip** - Exclude from campaign

5. **Complete Campaign**
   - Click "Submit Choices"
   - Approved messages are sent (or mocked)
   - Data persisted for future reference

### Example Input

```text
John Smith
Senior Software Engineer at TechCorp Inc.
San Francisco Bay Area

About:
Passionate about building scalable systems and mentoring teams.
10+ years in distributed systems, currently leading the platform team.
Love hiking, coffee, and bad programming jokes.

Experience:
- TechCorp Inc: Senior Software Engineer (2020-present)
- StartupXYZ: Backend Developer (2017-2020)

Interests: Kubernetes, System Design, Open Source
```

### Sample Output (Email)

```
Subject: Your distributed systems work at TechCorp caught my attention

Hi John,

I came across your profile and was impressed by your work leading 
the platform team at TechCorp. Your focus on scalable systems 
really resonates with challenges we're solving.

We're building something interesting in the infrastructure space 
and I think your experience with Kubernetes and distributed 
systems would give you a unique perspective.

Would you be open to a quick 15-minute chat this week? I'd love 
to share what we're working on and get your thoughts.

Best,
[Your Name]
```

---

## 📡 API Reference

### Base URL

```
http://localhost:8080/api/v1
```

### Endpoints

#### Start Campaign

```http
POST /campaigns
Content-Type: application/json

{
  "url": "https://linkedin.com/in/johndoe",
  "text": "Additional context about the person",
  "file_content": "base64_encoded_content (optional)"
}
```

**Response:**
```json
{
  "campaign_id": "abc123",
  "status": "running",
  "message": "Campaign started successfully"
}
```

#### Upload File

```http
POST /campaigns/upload
Content-Type: multipart/form-data

file: [PDF or DOC file]
```

**Response:**
```json
{
  "campaign_id": "abc123",
  "status": "running",
  "message": "File processed successfully"
}
```

#### Get Campaign Status

```http
GET /campaigns/{campaign_id}
```

**Response:**
```json
{
  "campaign_id": "abc123",
  "status": "approval",
  "current_stage": "approval",
  "target_company": "TechCorp Inc",
  "target_role": "Senior Software Engineer",
  "stages": {
    "ingestion": { "status": "completed", "message": "..." },
    "persona": { "status": "completed", "message": "..." },
    "drafting": { "status": "completed", "message": "..." },
    "scoring": { "status": "completed", "message": "..." },
    "approval": { "status": "running", "message": "Waiting for review" },
    "execution": { "status": "pending", "message": "" },
    "persistence": { "status": "pending", "message": "" }
  },
  "drafts": [
    {
      "channel": "email",
      "subject": "Your work caught my attention",
      "body": "Hi John...",
      "score": 8.5,
      "approved": false
    }
  ]
}
```

#### Submit Approvals

```http
POST /campaigns/{campaign_id}/approve
Content-Type: application/json

{
  "approved": ["email", "linkedin"],
  "regenerate": ["sms"],
  "skipped": ["instagram", "whatsapp"]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Approvals processed",
  "regenerated": ["sms"]
}
```

#### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "ollama": "connected",
  "database": "connected"
}
```

---

## 📁 Project Structure

```
outreach_engine/
├── app/
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI application
│   │   ├── routes.py             # API route handlers
│   │   ├── schemas.py            # Pydantic models
│   │   ├── state_manager.py      # Campaign state management
│   │   └── workflow_runner.py    # Async workflow execution
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── ingestion_agent.py    # Data ingestion node
│   │   ├── persona_agent.py      # Persona analysis node
│   │   ├── draft_agents.py       # 5 channel draft nodes
│   │   ├── scoring_agent.py      # Quality scoring node
│   │   ├── approval_agent.py     # Human approval node
│   │   ├── execution_agent.py    # Message sending node
│   │   └── persistence_agent.py  # Data storage node
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py              # TypedDict state definition
│   │   └── workflow.py           # LangGraph workflow builder
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── gmail_tool.py         # Gmail OAuth integration
│   │   ├── twilio_tool.py        # Twilio SMS integration
│   │   └── scraper_tool.py       # URL content fetcher
│   └── utils/
│       ├── __init__.py
│       ├── sanitizer.py          # PII sanitization
│       └── embeddings.py         # Embedding generation
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Main React component
│   │   ├── App.css               # Styles
│   │   ├── main.tsx              # Entry point
│   │   └── vite-env.d.ts         # TypeScript declarations
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── scripts/
│   └── init_db.py                # Database initialization
├── tests/
│   ├── test_agents.py
│   ├── test_workflow.py
│   └── test_api.py
├── .env.example                  # Example environment file
├── .gitignore
├── docker-compose.yml            # Docker services
├── Dockerfile.api                # API container
├── requirements.txt              # Python dependencies
├── setup.ps1                     # Windows setup script
├── setup.sh                      # Linux/Mac setup script
└── README.md                     # This file
```

---

## 🔧 Development

### Running Tests

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_workflow.py -v
```

### Code Quality

```powershell
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

### Adding a New Channel

1. **Create draft prompt** in `app/agents/draft_agents.py`:
   ```python
   _TWITTER_PROMPT = """..."""
   
   def draft_twitter_node(state: OutreachState) -> OutreachState:
       # Implementation
   ```

2. **Add to workflow** in `app/graph/workflow.py`:
   ```python
   graph.add_node("draft_twitter", draft_twitter_node)
   ```

3. **Add execution route** in `app/agents/execution_agent.py`:
   ```python
   def _route_twitter(draft: Dict) -> str:
       # Mock or real implementation
   ```

4. **Update frontend** in `frontend/src/App.tsx`:
   ```tsx
   const CHANNEL_ICONS: Record<string, string> = {
     // ...
     twitter: '🐦',
   };
   ```

### Database Migrations

```powershell
# Initialize Alembic (first time only)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head
```

---

## 🐛 Troubleshooting

### Common Issues

#### Ollama Connection Failed

```
Error: Could not connect to Ollama at http://localhost:11434
```

**Solution:**
```powershell
# Check if Ollama is running
ollama list

# Start Ollama service
ollama serve

# Verify connection
curl http://localhost:11434/api/tags
```

#### Model Not Found

```
Error: Model 'mistral' not found
```

**Solution:**
```powershell
# Pull the model
ollama pull mistral

# List available models
ollama list
```

#### Frontend Dependencies Missing

```
Error: Cannot find module 'react'
```

**Solution:**
```powershell
cd frontend
npm install
```

#### Database Connection Failed

```
Error: Could not connect to PostgreSQL
```

**Solution:**
```powershell
# Start PostgreSQL with Docker
docker-compose up -d postgres

# Check container status
docker ps

# View logs
docker logs outreach_postgres
```

#### Port Already in Use

```
Error: Address already in use :8080
```

**Solution:**
```powershell
# Find process using port
netstat -ano | findstr :8080

# Kill process (replace PID)
taskkill /PID <PID> /F
```

### Debug Mode

Enable detailed logging:

```ini
# .env
DEBUG=true
```

View LangGraph execution:

```python
# In workflow.py, add:
graph = workflow.compile(debug=True)
```

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

### Getting Started

1. **Fork the repository**

2. **Clone your fork**
   ```bash
   git clone https://github.com/yourusername/outreach_engine.git
   ```

3. **Create a branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

4. **Make changes and commit**
   ```bash
   git commit -m "Add amazing feature"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/amazing-feature
   ```

### Contribution Guidelines

- Follow existing code style
- Add tests for new features
- Update documentation as needed
- Keep commits atomic and well-described
- Ensure all tests pass before submitting

### Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [LangChain](https://langchain.com/) - LLM framework
- [LangGraph](https://github.com/langchain-ai/langgraph) - Workflow orchestration
- [Ollama](https://ollama.ai/) - Local LLM runtime
- [FastAPI](https://fastapi.tiangolo.com/) - API framework
- [React](https://reactjs.org/) - Frontend framework
- [ChromaDB](https://www.trychroma.com/) - Vector database

---

<div align="center">

**Built with ❤️ for the hackathon**

[⬆ Back to Top](#-outreach-engine)

</div>