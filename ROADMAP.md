# Flowdow Development Roadmap

This document outlines the evolutionary milestones for Flowdow from its architectural foundation to enterprise readiness.

---

## Phase 1: Foundation & Architecture (Current Milestone - v0.1.0)
- [x] Establish Modular Monolith directory structure.
- [x] Configure PostgreSQL database support via environment variables.
- [x] Define custom `User` model on `AbstractUser` before initial migrations.
- [x] Build core domain modules (`core`, `accounts`, `organizations`, `documents`, `templates_manager`, `data_sources`, `mapping`, `generation`, `audit`).
- [x] Implement Service Layer architecture separating HTTP handling from business logic.
- [x] Create modern, responsive B2B interface using Bootstrap 5 and clean typography.
- [x] Set up Docker & Docker Compose configuration for one-command local/production run.
- [x] Configure automated testing (`pytest`, `pytest-django`) and linting (`ruff`).
- [x] Author comprehensive foundational documentation (`README.md`, `PRD.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `AGENTS.md`, `DECISIONS.md`).

---

## Phase 2: Template Management & DOCX Ingestion (Current Milestone - v0.2.0)
- [x] Implement DOCX file upload, format checking, and security validation (magic bytes `PK\x03\x04`, zip bomb protection, 10MB size limits).
- [x] Build automatic placeholder detection using `docxtpl` / Jinja2 AST inspection (identifying `{{ variable_name }}` across split XML runs without code execution).
- [x] Template versioning: multi-version lifecycle (`draft`, `active`, `archived`) with collision-free storage paths (`v{version}_{token}_{slug}.docx`).
- [x] Interactive UI: Document Types catalog, detail page, template version history, and variable chip badges.
- [x] Template lifecycle actions: activation, archival, and safe DOCX download.
- [x] Role-based permission enforcement (read-only for `VIEWER`, modification rights for `OPERATOR`, `MANAGER`, `ADMIN`).
- [ ] Template placeholder metadata management (assigning custom validation rules and labels to variables).
- [ ] Template preview rendering with dummy data.

---

## Phase 3: Tabular Data Source Ingestion (Current Milestone - v0.3.0)
- [x] CSV file parser with automatic delimiter detection (comma, semicolon, tab, pipe) and encoding auto-detection (UTF-8, UTF-8 with BOM, Windows-1251).
- [x] XLSX file parser using `openpyxl` streaming `read_only=True` mode with multi-sheet selection.
- [x] Header extraction, duplicate/empty column validation, and dynamic `JSONField` persistence for `DataRecord`.
- [x] Interactive data preview table with pagination and detected column chips.
- [x] Centralized security limits: file size (20MB), max rows (50,000), max columns (200), zip-bomb decompression ratio checks.
- [x] Safe cascading deletion of `DataSource`, all `DataRecord` rows, and physical files with `AuditLog` compliance records.
- [x] Role-based access control (read-only for `VIEWER`, upload/delete rights for `OPERATOR`, `MANAGER`, `ADMIN`).
- [ ] Column statistics (empty cell counts, uniqueness checks).

---

## Phase 4: Visual Mapping Engine & Validation (v0.4.0)
- [ ] Interactive mapping UI: connect template placeholders on the left with dataset columns on the right.
- [ ] Rule configuration:
  - Required vs. optional fields.
  - Fallback default values when cells are empty.
  - Value transformations (uppercase, lowercase, title case, date formatting `YYYY-MM-DD` -> `DD.MM.YYYY`, currency formatting).
- [ ] Pre-generation dry-run validation:
  - Detect missing required values across rows.
  - Flag type mismatch errors before starting batch generation.

---

## Phase 5: Batch Generation Engine & Package Export (v0.5.0)
- [ ] Single document rendering engine with immediate download.
- [ ] Batch document generator processing all rows in the dataset.
- [ ] Document naming pattern configuration (e.g. `Contract_{{ employee_id }}_{{ last_name }}.docx`).
- [ ] Automatic ZIP packaging for batch results with downloadable progress.
- [ ] Generation batch dashboard with error logs for failed rows.

---

## Phase 6: REST API & Headless Operations (v0.6.0)
- [ ] Implement Django REST Framework API endpoints for:
  - `/api/v1/templates/`
  - `/api/v1/data-sources/`
  - `/api/v1/mappings/`
  - `/api/v1/generate/`
- [ ] API Token authentication for system integrations (ERP, CRM, external scripts).
- [ ] Webhook triggers upon batch completion.
- [ ] OpenAPI / Swagger documentation (`drf-spectacular`).

---

## Phase 7: Enterprise & Scale-Out (v1.0.0+)
- [ ] Background worker integration (Celery / Redis or Django-Q) for processing tens of thousands of documents concurrently.
- [ ] PDF conversion engine via headless LibreOffice or Gotenberg microservice.
- [ ] Audit log export and retention policies.
- [ ] Multi-user permission matrix (Admin, Manager, Operator, Viewer).
- [ ] Single Sign-On (SSO) via OpenID Connect / SAML2.

