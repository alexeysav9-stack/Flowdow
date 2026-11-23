# Flowdow — Open-Source Document Automation Platform

[![CI](https://github.com/flowdow/flowdow/actions/workflows/ci.yml/badge.svg)](https://github.com/flowdow/flowdow/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1-green.svg)](https://www.djangoproject.com/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**Flowdow** is a self-hosted, open-source web platform that automates repetitive document preparation from custom Word (`.docx`) templates and tabular datasets (`.csv`, `.xlsx`).

Designed for HR, legal, sales, finance, and operations teams, Flowdow empowers non-technical users to visually map variables, validate datasets, and generate individual or bulk document packages without writing code.

---

## ⚡ Try Flowdow in 60 Seconds (Ready-to-Use Demo)

Pre-built sample files are provided in [`examples/`](examples/):

> **Prerequisite:** Make sure **Docker Desktop** (Windows / macOS) or Docker Engine (Linux) is running before starting containers.

1. **Start the application** with Docker Compose:
   ```bash
   cp .env.example .env               # or: copy .env.example .env (Windows CMD)
   docker compose up -d --build
   docker compose exec web python manage.py createsuperuser
   ```
2. Open **http://localhost:8000** and log in.
3. **Upload Template:** Create document type `Employment Certificate` and upload [`examples/sample_certificate_eng.docx`](examples/sample_certificate_eng.docx) (or Russian [`examples/sample_certificate_ru.docx`](examples/sample_certificate_ru.docx)). Flowdow automatically detects `full_name`, `position`, `department`, `salary`, and `current_date`.
4. **Import Data:** Upload English dataset [`examples/sample_employees_eng.csv`](examples/sample_employees_eng.csv) / `.xlsx` (or Russian [`examples/sample_employees_ru.csv`](examples/sample_employees_ru.csv) / `.xlsx`).
5. **Create Mapping:** Map variables to table columns (`full_name` ➔ `Full Name` or `ФИО`, etc.).
6. **Generate:** Generate certificates for all rows and download a single ZIP package containing personalized `.docx` files!

See [`examples/README.md`](examples/README.md) for detailed step-by-step screenshots and guidelines.

---

## Key Features

- **Document & Template Management:** Create document types, upload `.docx` templates with auto-incrementing version control (`v1`, `v2`, ...), and manage lifecycles (`draft`, `active`, `archived`).
- **Deep Variable Discovery:** Jinja2 AST inspection of DOCX templates resolving Microsoft Word's internal split XML runs without executing untrusted code.
- **Tabular Data Ingestion (CSV & XLSX):**
  - **CSV:** Auto-detects delimiters (`,`, `;`, `\t`, `|`), handles standard UTF-8 and UTF-8 with BOM, and gracefully falls back to Windows-1251.
  - **XLSX:** Memory-efficient streaming parser (`openpyxl` with `read_only=True`) supporting multi-sheet selection and typed formatting.
- **Dynamic Schema Storage:** Uses PostgreSQL `jsonb` (`DataRecord.data`) allowing arbitrary column layouts without running database migrations.
- **Visual Mapping & Pre-Flight Validation:**
  - Pair template variables to dataset columns.
  - Set fallback default values and enforce mandatory required fields.
  - Built-in safe system variables (`current_date`, `current_datetime`, `current_year`, `system_platform`).
- **Resilient Batch Generation:**
  - Single document rendering or batch generation across thousands of rows.
  - **Error isolation:** a failure in row 5 will not interrupt row 6.
  - **Automated ZIP packaging:** all successfully rendered `.docx` files are compiled into a downloadable archive.
- **Audit & History:** Complete visibility into every batch, generation duration, success rate, and detailed error diagnostics.
- **Multilingual UI (RU / EN):** Seamless language switching for all interfaces.
- **Self-Hosted & Private:** Keep confidential customer data, contracts, and HR records strictly on your own servers.

---

### Supported DOCX Template Syntax

Flowdow processes Word `.docx` documents using `docxtpl`. Simple Jinja2 placeholder variables are supported:

```jinja2
{{ full_name }}
{{ position }}
{{ department }}
{{ salary }}
{{ current_date }}
```

- **Split Run Resolution:** Word frequently breaks placeholders across multiple XML runs (`<w:r><w:t>{{</w:t></w:r><w:r><w:t>var}}</w:t></w:r>`). Flowdow normalizes runs before extraction and rendering.
- **Security Invariant:** Template discovery utilizes non-evaluating Jinja2 AST analysis (`find_undeclared_variables`). Arbitrary Python evaluation and dunder attributes (`__class__`, `__subclasses__`) are strictly rejected.

---

## Tech Stack

- **Backend:** Python 3.12+, Django 5.1
- **Database:** PostgreSQL 16+ (via `psycopg` 3) / SQLite (for fast headless CI/testing)
- **Document Engine:** `docxtpl`, `python-docx`, `openpyxl`
- **Frontend:** Django Templates, Bootstrap 5.3, Bootstrap Icons, Vanilla JS
- **Containerization:** Docker, Docker Compose
- **Quality & Testing:** `pytest`, `pytest-django`, `ruff`

---

## Quickstart with Docker Compose

The recommended way to deploy Flowdow in production or local evaluation.

### Prerequisites

- **Windows / macOS:** Install and open **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**. Ensure the Docker engine is running (look for the green *Engine running* indicator in Docker Desktop). On Windows 10/11, the **WSL 2 backend** is strongly recommended.
- **Linux:** Install Docker Engine and the Compose plugin (`docker compose version`):
  ```bash
  sudo apt install docker.io docker-compose-v2   # Debian / Ubuntu
  ```

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/flowdow/flowdow.git
cd flowdow

# 2. Copy the environment configuration
cp .env.example .env               # Linux / macOS / Windows PowerShell
# or: copy .env.example .env       # Windows Command Prompt (CMD)

# 3. Start the application and database
docker compose up -d --build

# 4. Create an administrator account
docker compose exec web python manage.py createsuperuser
```

Once running, access the web interface at **http://localhost:8000**.

---

## Local Development Setup

### 1. Prerequisites
- Python 3.12+
- PostgreSQL 16+ (or Docker for database)
- `uv` (recommended) or `pip` / `venv`

### 2. Virtual Environment & Dependencies
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies including development tools
pip install -e ".[dev]"
```

### 3. Environment Variables
```bash
cp .env.example .env
# Adjust DB_NAME, DB_USER, DB_PASSWORD, DB_HOST in .env if needed
```

### 4. Database Migrations & Initial Setup
```bash
# With PostgreSQL (default):
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Or standalone with SQLite (zero database setup required):
DB_ENGINE=django.db.backends.sqlite3 python manage.py migrate
DB_ENGINE=django.db.backends.sqlite3 python manage.py createsuperuser
DB_ENGINE=django.db.backends.sqlite3 python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

---

## Running Tests & Code Quality

Flowdow requires 100% test pass and zero linting violations:

```bash
# Run test suite with pytest
pytest

# Run linter
ruff check .

# Run code formatter check
ruff format --check .
```

---

## Project Structure

```
Flowdow/
├── config/             # Core project configuration (settings, routing, wsgi, asgi)
├── apps/
│   ├── core/           # Base models, health check, dashboard metrics
│   ├── accounts/       # Custom User model, authentication, RBAC
│   ├── organizations/  # Single-tenant organization profile & settings
│   ├── documents/      # Document types catalog
│   ├── templates_manager/ # DOCX template storage & variable inspection
│   ├── data_sources/   # CSV / XLSX tabular data parser
│   ├── mapping/        # Variable-to-column mapping & validation
│   ├── generation/     # Single & batch document generation
│   └── audit/          # System audit trails
├── examples/           # Ready-to-use sample templates & datasets
├── locale/             # Gettext translation catalogs (RU / EN)
├── static/             # Static CSS and JavaScript assets
├── templates/          # Bootstrap 5 server-rendered HTML templates
├── tests/              # Pytest test suite (100+ tests)
├── .github/workflows/  # GitHub Actions CI pipeline
├── Dockerfile          # Container specification
├── docker-compose.yml  # Docker Compose orchestration
└── pyproject.toml      # Build metadata, dependencies & tool configs
```

---

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System Architecture, Boundaries & Layering
- [PRD.md](PRD.md) — Product Requirements Document
- [ROADMAP.md](ROADMAP.md) — Development Roadmap & Horizons
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution Guidelines
- [CHANGELOG.md](CHANGELOG.md) — Release Notes & Version History
- [DECISIONS.md](DECISIONS.md) — Architecture Decision Records (ADRs)
- [AGENTS.md](AGENTS.md) — Architectural Rules for Developers & AI Agents

---

## License

This project is licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for details.
