# DocuRAG AI

**Intelligent RAG-Powered Customer Support Platform with Document Intelligence & Automated Escalation**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-FF6B6B?style=for-the-badge)](https://qdrant.tech/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

**DocuRAG AI** is a production-grade, multi-tenant backend platform that lets businesses deploy sophisticated, document-grounded AI customer support chatbots on their websites in minutes.

It combines **Retrieval-Augmented Generation (RAG)**, intelligent intent detection, persistent conversation state management, and automated human escalation workflows into one secure, async-first system.

### Core Purpose
Enable companies to upload their knowledge base (product docs, code, policies, emails, spreadsheets) and instantly provide website visitors with accurate, source-cited AI answers — while intelligently routing complaints, capturing leads, and escalating to humans with full context.

### Target Users
- SaaS & product companies wanting self-hosted AI support
- Support & success teams seeking grounded, hallucination-resistant answers
- Developers needing a complete RAG + workflow engine they can embed anywhere

### Technical Goals
- Strict multi-tenant data isolation (user-scoped vectors + database filters)
- High-performance async architecture ready for production load
- Seamless human-AI handoff with rich context
- Simple embeddable widget integration with domain whitelisting
- Enterprise-grade secret management, logging, and observability

---

## Features

### Core Capabilities
- **Multi-format Document Intelligence** — Ingest PDFs, DOCX, 25+ code languages, Excel/CSV, and .eml files with specialized parsers and chunkers.
- **Advanced Semantic Chunking** — Lightweight, dependency-free semantic chunking for text + intelligent brace-aware chunking for codebases.
- **Stateful Conversation Engine** — Per-visitor state machine (`NEW` → `ACTIVE` → `HANDLING_COMPLAINT` → `EXTRACTING_CONTACT` → `ESCALATED`) persisted in PostgreSQL.
- **Smart Intent Detection** — Keyword-based routing for complaints, buying intent, contact requests, and decision signals.
- **Automated Escalation** — On complaint flow, captures phone/email and sends rich email to the business owner containing full chat history + context (async background task).
- **Embeddable Chat Widget** — Single `<script>` tag integration via `/widget.js`. Works on any website with client token + origin validation.

### AI & RAG Features
- **Hybrid LLM Orchestration** — Primary: Gemini 2.5 Flash Lite. Automatic fallback to Groq Llama-3.3-70B on rate limits/quota exhaustion.
- **High-Quality Embeddings** — Gemini Embedding 2 (3072 dimensions) stored in Qdrant with cosine similarity.
- **Grounded Responses** — Every answer includes labeled document sources. System prompt enforces structure, scannability, empathy, and escalation suggestions when information is missing.
- **Chat History Injection** — Last 6 turns automatically included for coherent multi-turn conversations.

### Security & Operations
- JWT authentication for admin dashboard
- Per-tenant origin/domain whitelisting
- Strict user isolation at Qdrant payload filter + PostgreSQL foreign keys
- Argon2 password hashing
- Rate limiting on sensitive endpoints (FastAPI Limiter + Redis)
- File upload guards (15 MB limit, blacklisted dangerous extensions)
- Doppler-first secret management with `.env` fallback
- Structured JSON logging with rotating files and rich context (function name + line numbers)

### Performance & Scalability
- Fully asynchronous request handling
- `run_in_executor` for CPU-bound file parsing
- Redis caching for document metadata (600s TTL with smart invalidation)
- Batch vector upserts to Qdrant
- Payload indexes on `user_id` and `document_id` for fast filtered search
- Background task for email escalation

---

## Tech Stack

### Backend
| Component              | Technology                          | Role |
|------------------------|-------------------------------------|------|
| Web Framework          | FastAPI 0.112+                      | Async API server with lifespan events |
| ASGI Server            | Uvicorn                             | Production ASGI server |
| Authentication         | python-jose + Argon2-cffi           | JWT tokens + secure password hashing |
| Rate Limiting          | fastapi-limiter + Redis             | Endpoint protection |
| File Handling          | python-multipart + tempfile         | Secure upload processing |

### AI / ML
| Component              | Technology                          | Role |
|------------------------|-------------------------------------|------|
| Primary Chat Model     | Google Gemini 2.5 Flash Lite        | Main response generation |
| Fallback Chat Model    | Groq Llama-3.3-70B Versatile        | Automatic failover on rate limits |
| Embeddings             | Gemini Embedding 2 (3072 dim)       | Vector generation |
| Orchestration          | Custom RAG pipeline                 | Retrieval, prompt construction, fallback logic |

### Database & Storage
| Component              | Technology                          | Role |
|------------------------|-------------------------------------|------|
| Primary Database       | PostgreSQL + SQLAlchemy             | Users, documents, chat history, client state |
| Vector Database        | Qdrant                              | User-isolated semantic search |
| Cache / Rate Limit     | Redis                               | Document metadata cache + FastAPI Limiter backend |

### Infrastructure & DevOps
| Component              | Technology                          | Role |
|------------------------|-------------------------------------|------|
| Secret Management      | Doppler + python-dotenv             | Production secrets with local fallback |
| Logging                | Custom AdvancedLogger               | Console + rotating UTF-8 files with rich context |
| Email Escalation       | smtplib (Gmail SMTP)                | Async background escalation emails |

---

## Project Architecture


### Data Flow Summary
1. **Upload Path**: JWT-protected → Parse file (async) → Semantic/Code chunking → Gemini embeddings → Batch upsert to Qdrant (with `user_id` + `document_id` payload) → Store metadata in Postgres → Invalidate Redis cache.
2. **Chat Path**: Widget → Origin + client_token validation → Load/create visitor state → Intent detection → Either RAG retrieval + LLM or special complaint flow → Background email if escalated → Persist turns → Return structured response.
3. **Isolation**: Every vector and database record is strictly filtered by `user_id`. Origin domain must match user's configured `allowed_url`.

---

## Folder Structure

```bash
docurag-ai/
├── Security/
│   ├── Advance_Logger.py          # Rich structured logger (console + rotating UTF-8 files)
│   ├── get_secretes.py            # Doppler-first secret loader with graceful env fallback
│   └── JWT_token.py               # JWT creation & decoding helpers
│
├── RAG/
│   ├── EmbeddingsGenerationnStorage.py   # Core orchestrator: RAG, intent detection, state machine, escalation
│   ├── Gemini_Api_connection.py          # Gemini + Groq client with automatic rate-limit fallback
│   └── Vector_Store.py                   # Qdrant client (user-isolated CRUD + indexes)
│
├── DATABASE/
│   ├── SQL_Database.py            # SQLAlchemy + raw SQL: users, documents, clients, chat_history
│   └── Redis_Connection.py        # Redis pool, JSON caching, FastAPI Limiter backend
│
├── Files_Management/
│   └── Files_Parser.py            # Multi-format parsers (PDF, DOCX, code, Excel, EML) + chunkers
│
├── Frontend_Connection.py         # Main FastAPI app (all routes, dependencies, lifespan, widget serving)
│
├── templates/
│   ├── landing.html
│   ├── login.html
│   ├── signin.html
│   └── dashboard.html             # Admin interface for documents, clients, settings
│
├── static/
│   └── widget.js                  # Embeddable chat widget (served at /widget.js)
│
├── requirements.txt
├── README.md
├── Dockerfile (recommended)
├── docker-compose.yml (recommended)
└── .env.example
---

## Purpose of Major Folders

- Security/: All authentication, secret loading, and observability concerns.
- RAG/: Complete retrieval-augmented generation and conversation orchestration layer.
- DATABASE/: Persistent storage abstractions (relational + cache).
- Files_Management/: Document ingestion and intelligent chunking pipeline.


### Installation
### Prerequisites

-    Python 3.11+ (recommended)
-    PostgreSQL 14+
-    Redis 7+
-    Qdrant (self-hosted or cloud)
-    Doppler CLI (optional but recommended for production)

## Steps (Linux / macOS / Windows WSL)
```
# 1. Clone repository
git clone https://github.com/your-org/docurag-ai.git
cd docurag-ai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (PowerShell)
```
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment Variables
```
# === Core Infrastructure ===
DATABASE_URL=postgresql://user:password@localhost:5432/docurag
REDIS_HOST=redis://localhost:6379/0

QDRANT_URL=https://your-qdrant-instance.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key

# === AI Providers ===
GEMINI_API_KEY=your-gemini-api-key
GROQ_API_KEY=your-groq-api-key

# === Authentication ===
JWT_SECRETE=your-super-long-random-jwt-secret
JWT_ALGORITHM=HS256

# === Escalation Email (Gmail App Password recommended) ===
SUPPORT_EMAIL_SENDER=support@yourcompany.com
SUPPORT_EMAIL_PASSWORD=your-gmail-app-password

# === Doppler (Production - overrides .env when present) ===
DOPPLER_TOKEN=dp.st.xxxxxxxxxxxxxxxxxxxxxxxx
DOPPLER_PROJECT=docurag
DOPPLER_CONFIG=prod
```

Running the Project
Development
Bashuvicorn Frontend_Connection:app --reload --host 0.0.0.0 --port 8000
Production (recommended)
Bashuvicorn Frontend_Connection:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools
Or use Gunicorn with Uvicorn workers:
Bashgunicorn Frontend_Connection:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
With Docker (Recommended for Production)
Bashdocker-compose up -d --build

API Documentation
Authentication

Dashboard routes: Authorization: Bearer <JWT>
Chat route (/chat): client_token in request body + HTTP Origin / Referer header must match the user's configured allowed_url.

Main Endpoints


















































































MethodPathAuthDescriptionKey Request FieldsPOST/loginNoneUser loginemail, passwordPOST/signinNoneCreate new accountname, url, email, passwordGET/getSettingsJWTGet allowed URL + client token—POST/updateUrlJWTUpdate allowed deployment domainallowed_urlPOST/addDocumentJWTUpload & index files (multi-file)files[] (multipart)POST/show_documentsJWTList user's documents (cached)—POST/delete_documentJWTDelete document + vectorsDocument_idPOST/getclientsdataJWTGet client/lead data—POST/chatclient_tokenMain widget chat endpointclient_token, visitor_id, messageGET/widget.jsNoneServe embeddable widget—
Example Chat Request
JSONPOST /chat
{
  "client_token": "550e8400-e29b-41d4-a716-446655440000",
  "visitor_id": "visitor_abc123",
  "message": "How do I upgrade my plan?"
}
Example Successful Response
JSON{
  "reply": "Great question! Here's how to upgrade your plan:\n\n• Go to Billing → Plans\n• Select Pro tier\n• Click **Upgrade Now**\n\nYou're all set! 🚀"
}

Database Schema
PostgreSQL Tables
users

id (PK), user_id (UUID), url (allowed base domain), name, email (unique), password (Argon2 hashed)

documents

id (PK), user_id (FK → users), file_name, extension, created_at

clients

id (PK), user_id (FK), visitor_id, email, phone, state (NEW/ACTIVE/HANDLING_COMPLAINT/EXTRACTING_CONTACT/ESCALATED), created_at

chat_history

id (PK), user_id (FK), visitor_id, role (user/model), message, created_at
Index: (user_id, created_at DESC)

Qdrant Collection: documents

Vector size: 3072 (Gemini Embedding 2)
Distance: Cosine
Payload indexes: user_id (INTEGER), document_id (INTEGER)
Every point also stores: text (chunk content)

All queries are hard-filtered by user_id at the Qdrant engine level.

AI / LLM System
Models

Chat (Primary): gemini-2.5-flash-lite
Chat (Fallback): llama-3.3-70b-versatile via Groq
Embeddings: gemini-embedding-2 (3072 dimensions)

RAG Pipeline

User query → Gemini embedding
Qdrant search filtered by user_id (top 4 chunks)
Deduplication + truncation
Prompt assembly:
Detailed system instruction (structured, empathetic, scannable)
Labeled document sources
Recent chat history (last 6 turns)
Customer query + required answer structure

LLM generation (with automatic Groq fallback on rate limit errors)

Prompt Philosophy
Enforces:

Friendly yet professional tone
Heavy use of bullet points and bold terms
Clear next steps
Escalation suggestion when information is missing from documents


Security

Authentication: JWT (7-day expiry) for dashboard; short-lived client tokens for widgets
Authorization: Every database and vector operation filtered by authenticated user_id
Domain Protection: Strict Origin / Referer validation against per-user allowed_url
Password Security: Argon2 hashing
Secret Management: Doppler (production) with encrypted .env fallback
Input Validation: File extension blacklist, size limits (15 MB), text sanitization
Rate Limiting: Applied to login, signin, and document upload endpoints
Logging: No sensitive data in logs; structured context for debugging


Performance Optimizations

Fully async FastAPI + run_in_executor for blocking I/O
Redis-backed document list caching with instant invalidation
Batch vector insertion to Qdrant
Payload indexes for lightning-fast user filtering
Limited chat history window (last 6 turns)
Background email sending via asyncio.create_task


Deployment
Recommended: Docker Compose
Include services for postgres, redis, qdrant, and the app. Use Doppler or mounted .env for secrets.
Cloud Platforms

Railway / Render / Fly.io: Excellent FastAPI support + one-click Postgres/Redis add-ons. Use Qdrant Cloud.
AWS / GCP / Azure: Use managed PostgreSQL, ElastiCache/Redis, and Qdrant Cloud or self-hosted on Kubernetes.
VPS: Docker Compose + Nginx reverse proxy + systemd or Dokku.

Environment-Specific Tips

Set DOPPLER_TOKEN in production for zero-secret-in-git workflow.
Use at least 2–4 Uvicorn workers in production.
Enable Redis persistence and Qdrant snapshots for durability.


CI/CD (GitHub Actions Example)
YAMLname: CI/CD

on:
  push:
    branches: [ main ]

jobs:
  test-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Lint
        run: flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
      - name: Deploy to Railway
        run: railway up --detach

Usage Examples
Embed Widget on Your Site
HTML<script 
  src="https://your-docurag-instance.com/widget.js" 
  data-client-token="550e8400-e29b-41d4-a716-446655440000">
</script>
Python Integration Example
Pythonimport requests

response = requests.post(
    "https://your-instance.com/chat",
    json={
        "client_token": "your-client-token",
        "visitor_id": "visitor_xyz",
        "message": "What are your pricing plans?"
    }
)
print(response.json()["reply"])

Troubleshooting


















































IssueLikely CauseSolutionModuleNotFoundErrorMissing dependenciespip install -r requirements.txtQdrant connection errorsWrong URL or API keyVerify in Doppler / .envGemini rate limit errorsQuota exhaustedFallback to Groq should trigger automaticallyFile upload fails>15MB or blacklisted extensionCheck file size and typeJWT "Invalid token"Secret mismatch or expired tokenRegenerate token or check JWT_SECRETEChat returns generic errorMissing documents or embedding failureUpload documents first via dashboardPort 8000 already in useAnother service runningChange port or kill processEscalation email not sentSMTP credentials missing or Gmail blocksUse App Password + enable "Less secure apps" (or use transactional email service)

Roadmap

React-based modern admin dashboard
Advanced analytics (escalation rate, popular queries, satisfaction)
Webhook support for escalation (Slack, Linear, Zendesk)
Multi-LLM support (Claude, OpenAI, self-hosted)
Image/PDF OCR ingestion
Usage-based billing & tenant quotas
Kubernetes Helm chart + auto-scaling
Voice interface via ElevenLabs / Deepgram
Fine-grained citation highlighting in widget


Contribution Guide

Fork the repository
Create a feature branch: git checkout -b feature/amazing-improvement
Commit using conventional commits (feat:, fix:, docs:)
Ensure all new code includes proper logging and error handling
Open a Pull Request with clear description and screenshots where applicable

We follow PEP 8 + Black formatting and expect comprehensive docstrings on public methods.

License
This project is licensed under the MIT License — see the LICENSE file for details.
You are free to use, modify, and distribute this software for personal and commercial purposes.

Author & Contact
DocuRAG AI was built to solve real-world customer support automation challenges with production-grade reliability.
For questions, feature requests, or enterprise support:

Open an issue on GitHub
Email: support@your-docurag-domain.com (replace with your instance)

Built with precision, performance, and practicality in mind.

Last updated: June 2026
text**Copy the entire block above** — it is a complete, production-ready `README.md` ready to paste