# Flowdow — Open-Source Document Automation Platform

Flowdow is a modern, self-hosted web application that automates repetitive document preparation from custom DOCX templates and tabular data sources (CSV, XLSX).

Designed for HR, legal, sales, finance, and operational teams, Flowdow empowers business users to visually map variables, validate datasets, and generate individual or bulk document packages without writing code.

---

## Key Features

- **Document & Template Management:** Create document types, upload DOCX templates with version control (`v1`, `v2`), and automatically extract variables.
- **Automatic Variable Detection:** Deep AST inspection of DOCX templates resolving Word's internal split XML runs.
- **Multi-Version Lifecycle:** Versioning (`draft`, `active`, `archived`) with collision-proof storage paths preventing file overwriting.
- **Enterprise Security:** Strict file validation (magic bytes `PK\x03\x04`, zip bomb protection, 10MB limit), path traversal defense, and role-based access control.
- **Multilingual UI (RU / EN):** Instant language switching for all management screens.
- **Tabular Data Ingestion (Upcoming):** Import spreadsheet data from CSV and XLSX files with automatic column detection.
- **Variable Mapping & Validation (Upcoming):** Map template variables to data columns with default fallback values and pre-flight validation.
- **Single & Batch Generation (Upcoming):** Generate single documents on demand or package thousands of personalized documents into a single ZIP archive.
- **Modular Monolith Architecture:** Clean layered design (Presentation, Service Layer, Business Modules, Infrastructure).
- **Audit & History:** Full visibility into who generated which documents, with which template, and when.
- **Self-Hosted & Private:** Keep corporate data, contracts, and personal records safely within your own infrastructure.

---

### Supported DOCX Template Syntax

Flowdow processes Word `.docx` documents using `docxtpl`. At this stage, simple placeholder variables are supported:

```jinja2
{{ full_name }}
{{ group }}
{{ specialty }}
{{ issue_date }}
```

- **Split Run Resolution:** Word often divides text into multiple `<w:r><w:t>` elements during editing. Flowdow cleans and unifies these runs, accurately discovering variables.
- **Security Invariant:** Template discovery uses non-evaluating Jinja2 AST analysis (`find_undeclared_variables`). Execution of arbitrary Python code or dangerous dunder attributes is completely blocked.

---

## Tech Stack

- **Backend:** Python 3.12+, Django 5.1
- **Database:** PostgreSQL 16+ (via `psycopg` 3)
- **Document Engine:** `docxtpl`, `python-docx`, `openpyxl`
- **Frontend:** Django Templates, Bootstrap 5.3, Bootstrap Icons, Vanilla JS
- **Containerization:** Docker, Docker Compose
- **Quality & Testing:** `pytest`, `pytest-django`, `ruff`

---

## Quickstart with Docker Compose

The fastest way to launch Flowdow with PostgreSQL is using Docker Compose:

```bash
# 1. Clone the repository
git clone https://github.com/your-org/flowdow.git
cd flowdow

# 2. Copy the environment configuration
cp .env.example .env

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
uv venv --python 3.12 .venv
source .venv/bin/activate

# Install dependencies including development tools
uv pip install -e ".[dev]"
```

### 3. Environment Variables
```bash
cp .env.example .env
# Adjust DB_NAME, DB_USER, DB_PASSWORD, DB_HOST in .env if needed
```

### 4. Database Migrations
```bash
python manage.py migrate
```

### 5. Create Superuser & Run Development Server
```bash
python manage.py createsuperuser
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

---

## Data Sources & Tabular Ingestion (CSV / XLSX)

Flowdow includes a tabular data ingestion engine designed to import structured spreadsheets without schema migrations:

- **Supported Formats:**
  - **CSV:** Decoded with `utf-8-sig` (transparently supporting standard UTF-8 and UTF-8 with BOM, with fallback to Windows-1251). Delimiters (`,`, `;`, `\t`, `|`) are auto-detected via `csv.Sniffer` and frequency analysis.
  - **XLSX:** Parsed via `openpyxl` in memory-efficient streaming mode (`read_only=True, data_only=True`), supporting multi-sheet selection and date/number formatting.
- **Header & Structure Validation:**
  - First non-empty row serves as column headers.
  - Headers must be unique and non-empty.
  - Leading, intermediate, and trailing empty lines are automatically skipped.
  - Rows with excess undeclared values raise descriptive record-level errors, preventing silent data loss.
- **Dynamic Storage via `JSONField`:**
  - Ingested rows are stored in `DataRecord.data` as a dynamic JSON object (`{"ФИО": "Иванов И.И.", "Оклад": "120000"}`).
  - Backed by PostgreSQL `jsonb` for high performance, indexing, and direct 1:1 mapping into template contexts without dynamic database tables.
- **Security & Limits:**
  - Max upload size: 20 MB.
  - Max rows: 50,000 rows per dataset (DoS protection).
  - Max columns: 200 columns.
  - XLSX archive inspection: magic bytes `PK\x03\x04`, OpenXML structure verification, executable payload rejection, and zip-bomb decompression ratio checks.

---

## Running Tests & Code Quality

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
├── config/             # Core project configuration (settings, routing, wsgi)
├── apps/
│   ├── core/           # Base models, dashboard metrics, shared services
│   ├── accounts/       # Custom User model, authentication, profiles
│   ├── organizations/  # Single-tenant organization profile & settings
│   ├── documents/      # Document types catalog
│   ├── templates_manager/ # DOCX template storage & variable inspection
│   ├── data_sources/   # CSV / XLSX tabular data parser
│   ├── mapping/        # Variable-to-column mapping & validation
│   ├── generation/     # Single & batch document generation
│   └── audit/          # System audit trails
├── static/             # Static CSS and JavaScript assets
├── templates/          # Bootstrap 5 server-rendered HTML templates
├── tests/              # Pytest test suite
├── Dockerfile          # Container specification
├── docker-compose.yml  # Docker Compose orchestration
└── pyproject.toml      # Build metadata, dependencies & tool configs
```

---

## Documentation

- [PRD.md](PRD.md) — Product Requirements Document
- [ARCHITECTURE.md](ARCHITECTURE.md) — System Architecture & Layering
- [ROADMAP.md](ROADMAP.md) — Development Roadmap & Horizons
- [AGENTS.md](AGENTS.md) — Rules & Invariants for Developers & AI Agents
- [DECISIONS.md](DECISIONS.md) — Architecture Decision Records (ADRs)

---

## License

This project is licensed under the Apache 2.0 License.

