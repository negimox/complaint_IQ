# ComplaintIQ — AI-Powered Customer Complaint Management System

ComplaintIQ is a pharmaceutical Quality Management System (QMS) complaint intake and triage platform built in compliance with **21 CFR Part 211.198** and **ICH Q9/Q10** quality risk management standards. It replaces manual, error-prone complaint logging with an automated, multi-agent AI pipeline and an immutable audit trail.

---

## Live Deployments & Video Demonstrations

| Resource | Link |
|---|---|
| **Live Web Application (Vercel)** | [https://complaint-iq-delta.vercel.app](https://complaint-iq-delta.vercel.app) |
| **Backend API Documentation (Render)** | [https://complaint-iq-backend.onrender.com/docs](https://complaint-iq-backend.onrender.com/docs) |
| **Video 1: Working Product Demonstration** | [Watch on Google Drive](https://drive.google.com/file/d/1rIRTuuRHK4G2iehMvdQwc2CxbZCFjtot/view?usp=sharing) |
| **Video 2: Codebase & Architecture Walkthrough** | *(Separate submission link)* |

---

## System Architecture

```mermaid
flowchart LR
    subgraph Client [React 19 + Redux Toolkit]
        UI[Two-Pane Complaint UI]
        SSE[SSE Event Listener]
    end

    subgraph Backend [FastAPI Server]
        API[API Endpoints]
        Router[Router Node]
        DocLoader[Document Loader]
        Extractor[Entity Extractor]
        Validator[Validator Node]
        Synth[Description Synthesizer]
        Risk[Risk & CAPA Assessor]
        Correction[Correction Loop]
    end

    subgraph Storage [Supabase / PostgreSQL]
        DB[(PostgreSQL)]
        Vectors[(pgvector Embeddings)]
        Audit[(21 CFR Audit Log)]
    end

    UI -->|PDF / EML / DOCX / Text| API
    API --> Router
    Router --> DocLoader --> Extractor --> Validator --> Synth --> Risk
    Risk -->|SSE Stream| SSE --> UI
    UI -->|Conversational Corrections| Correction --> DB
    Correction -->|Audit Diff| Audit
    UI -->|Commit to Ledger| DB
    DB --> Vectors
```

---

## Key Features

- **Multi-Modal Document & Text Ingestion**: Ingests complaints via PDF, DOCX, TXT, EML, or raw text paste with live extraction progress via Server-Sent Events (SSE).
- **LangGraph Multi-Agent Pipeline**: Specialized nodes extract 12+ pharmaceutical entities, validate QMS constraints (batch patterns, NDC format, dates), and synthesize formal regulatory complaint descriptions.
- **ICH Q9 & Q10 Risk Assessment**: Automatically determines severity (*Critical*, *Major*, *Minor*), recommended regulatory actions, root-cause hypotheses, and CAPA recommendations.
- **Conversational Correction Loop**: Natural language chat allows QA analysts to adjust fields interactively; changes are diffed and previewed with real-time UI highlight animations.
- **21 CFR Part 211.198 Compliance**: Once committed to the QMS ledger, records are permanently locked. Post-commit mutations return HTTP 403 Forbidden. Every pre-commit modification is recorded in an immutable `audit_log` trail.
- **Vector-Based Duplicate Detection**: Uses `sentence-transformers` embeddings stored in PostgreSQL `pgvector` to detect similar historical complaints and calculate cosine similarity scores.
- **Pre-Commit Completeness Checker**: Validates 8 essential integrity fields before permitting commitment to the QMS ledger.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Redux Toolkit, Vite, Vanilla CSS Design System, Google Inter font |
| **Backend** | FastAPI, LangGraph, SQLAlchemy 2.0 (Async), Alembic, Pydantic v2 |
| **Database** | PostgreSQL on Supabase with `pgvector` extension |
| **AI / LLM** | Groq (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`), `sentence-transformers` |
| **Document Parsers** | `pdfplumber`, `python-docx`, `pytesseract` OCR, Python `email` library |

---

## Environment Variables

Create `.env` files in both `backend/` and `frontend/` (see `.env.example`):

### Backend (`backend/.env`)
```ini
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL_EXTRACT=openai/gpt-oss-20b
GROQ_MODEL_RISK=openai/gpt-oss-120b
DATABASE_URL=postgresql://user:password@host:5432/postgres?sslmode=require
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
SECRET_KEY=generate_with_openssl_rand_hex_32
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Frontend (`frontend/.env`)
```ini
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_NAME=ComplaintIQ
```

---

## Quick Start (Local Setup)

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL instance with `vector` extension (e.g., Supabase)

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API Documentation: `http://localhost:8000/docs`

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Client URL: `http://localhost:5173`

---

## Testing

The backend includes a comprehensive automated test suite covering validation logic, conversational diffs, 21 CFR 211.198 immutability, and API endpoints:

```bash
cd backend
pytest -v
```

---

## Project Structure

```text
complaint_IQ/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph graph & specialized nodes
│   │   ├── api/routes/      # FastAPI endpoints (complaints, copilot)
│   │   ├── core/            # Config, DB connection, logging
│   │   ├── models/          # SQLAlchemy ORM models
│   │   └── schemas/         # Pydantic validation schemas
│   ├── alembic/             # Database migrations
│   ├── sample_data/         # Sample PDF & text test files
│   └── tests/               # Pytest suite
├── frontend/
│   ├── src/
│   │   ├── components/      # Modular UI components (Cards, Form, Chat)
│   │   ├── pages/           # Complaint intake page
│   │   ├── store/           # Redux Toolkit slices
│   │   └── services/        # API and SSE streaming clients
└── reference_files/         # Requirements and SRS specifications
```
