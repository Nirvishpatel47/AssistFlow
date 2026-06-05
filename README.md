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
```
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
