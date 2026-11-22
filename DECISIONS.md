# Architecture Decision Records (ADRs) — Flowdow

This document tracks all significant architectural decisions, their context, rationale, and consequences for the Flowdow project.

---

## ADR 0001: Modular Monolith Architecture Pattern

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Flowdow is an open-source document preparation platform intended to be self-hosted by companies ranging from small businesses to enterprise IT departments. We need an architecture that scales in functionality without adding operational complexity (such as distributed service coordination, RPC latency, network partitions, or multi-container orchestration headaches).
- **Decision:**
  We adopt the **Modular Monolith** pattern. All business domains (`accounts`, `organizations`, `documents`, `templates_manager`, `data_sources`, `mapping`, `generation`, `audit`) reside within a single Django repository inside the `apps/` directory, adhering to strict module boundaries.
- **Consequences:**
  - *Positive:* Simple deployment via single Docker container or standard Python process; zero network serialization overhead between modules; straightforward transactional integrity via database transactions; easy debugging and local development.
  - *Negative:* Requires developer discipline to enforce boundaries and prevent unintended coupling between modules.

---

## ADR 0002: Service Layer Pattern to Decouple Business Operations

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Traditional Django applications often suffer from "fat models" or "fat views", where domain logic, validation, file operations, and orchestration are tangled directly inside `views.py`. This hinders testability and code re-use (e.g. when adding CLI commands or REST API endpoints in future versions).
- **Decision:**
  We enforce an explicit **Service Layer** (`apps/<module>/services.py`). Views act strictly as thin HTTP controllers: they authenticate requests, validate input via Django Forms, invoke service methods, and render responses or issue redirects. Business operations, document rendering, and batch processing live exclusively in services.
- **Consequences:**
  - *Positive:* High testability without requiring HTTP request mocking; clean transition to future REST/GraphQL endpoints by calling identical services; clear separation of concerns.
  - *Negative:* Introduces an additional file and layer of indirection for simple CRUD actions.

---

## ADR 0003: Custom User Model (`accounts.User`) from Project Inception

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Django strongly recommends configuring a custom user model extending `AbstractUser` before running the very first database migration. Swapping out the user model mid-project causes severe database migration breakage and foreign key headaches.
- **Decision:**
  We define `accounts.User(AbstractUser)` in `apps/accounts/models.py` and set `AUTH_USER_MODEL = 'accounts.User'` in `config/settings.py` prior to running any database migration.
- **Consequences:**
  - *Positive:* Enables custom user fields (e.g., job title, phone, organization role, avatar) at any point in the future without database rebuilds.
  - *Negative:* None; standard Django best practice.

---

## ADR 0004: Single-Tenant Instance Model for Version 1.0

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Many corporate users require strict physical isolation of their documents, HR files, and financial agreements. Building full multi-tenant schema routing or row-level tenant filtering introduces significant architectural overhead and risk of accidental data leakage.
- **Decision:**
  Flowdow Version 1.0 operates on a single-tenant deployment model: one installation serves one organization. The `organizations` module manages the workspace's company details, branding, and defaults.
- **Consequences:**
  - *Positive:* Vastly simpler data queries; eliminates tenant leakage bugs; allows self-hosters to deploy separate containers for different departments or legal entities with isolated databases.
  - *Negative:* Multi-client SaaS hosting requires multiple container instances or future tenancy migration.

---

## ADR 0005: Server-Side Rendered Django Templates with Bootstrap 5

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  We need a fast, responsive, and minimalist B2B user interface. Modern JavaScript frameworks (React, Vue) add significant toolchain complexity (Node.js, Webpack/Vite, package bloat, API boilerplate, CORS).
- **Decision:**
  We use standard Django Templates coupled with **Bootstrap 5.3** and native vanilla JavaScript.
- **Consequences:**
  - *Positive:* Zero frontend build step; instantaneous page rendering; lower resource consumption; simplified deployment; clean responsive layouts with Bootstrap components.
  - *Negative:* Rich interactive drag-and-drop or visual mapping requires focused vanilla JS widgets rather than off-the-shelf React libraries.

---

## ADR 0006: PostgreSQL with `psycopg` 3 as the Primary Database Engine

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Flowdow requires rock-solid ACID transactions, native JSON field support (for storing parsed template variables, mapping rules, and audit metadata), and concurrency.
- **Decision:**
  We select PostgreSQL 16+ as the standard database, accessed via the modern `psycopg` 3 driver (`django.db.backends.postgresql`).
- **Consequences:**
  - *Positive:* Native `JSONField` querying and indexing; production concurrency; robust backup and restore ecosystems.
  - *Negative:* Requires running a PostgreSQL container or local daemon for local development.

---

## ADR 0007: Docker Compose as Canonical Deployment & Development Harness

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Self-hosters need a reproducible, zero-friction way to run Flowdow alongside PostgreSQL without manually installing system dependencies.
- **Decision:**
  We provide a production-ready `Dockerfile` and `docker-compose.yml` that provisions PostgreSQL, applies database migrations, and exposes the web application on port 8000 with persistent data volumes.
- **Consequences:**
  - *Positive:* One command setup (`docker compose up -d`); zero dependency conflicts; clear blueprint for production orchestration.

---

## ADR 0008: DOCX Template Variable Discovery via `docxtpl` and AST Inspection

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Microsoft Word documents internally fragment text runs into multiple `<w:r><w:t>` elements (e.g. spellchecking, formatting, or cursor pauses split `{{ employee_name }}` across separate runs). Naive regex searches across raw XML fail on fragmented runs or false-match internal XML attributes. Furthermore, executing arbitrary Python or Jinja expressions from uploaded templates poses severe security vulnerabilities (RCE).
- **Decision:**
  We utilize `docxtpl.DocxTemplate.get_undeclared_template_variables()`, which merges split XML text runs and uses Jinja2 AST parsing (`jinja2.meta.find_undeclared_variables`) without executing any code. Extracted variable names are strictly validated against identifier rules (`^[a-zA-Z_][a-zA-Z0-9_]*$`), disallowing dunder attributes and built-in keywords.
- **Consequences:**
  - *Positive:* 100% accurate variable extraction across fragmented Word XML runs; zero arbitrary code execution risk; clean error reporting for syntax mistakes.
  - *Negative:* Only standard Jinja2 placeholder tags are analyzed in Phase 2.

---

## ADR 0009: DocumentType and Template One-to-Many Versioning Lifecycle

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Organizations regularly update template texts, legal clauses, and branding. Overwriting old files causes loss of auditability and breaks existing batches or mappings.
- **Decision:**
  We separate `DocumentType` (stable domain identity) from `Template` (versioned file revisions). Uploading a new template automatically increments the integer `version` (v1, v2, v3...) and stores the file under a UUID-scoped non-overwriting path (`templates/<id>/v<version>_<token>_<slug>.docx`). Each version carries an explicit status (`draft`, `active`, `archived`). Activating a version automatically archives previous active versions for that document type.
- **Consequences:**
  - *Positive:* Complete version history; old files can never be overwritten; single active version guarantee per DocumentType; reversible rollbacks.
  - *Negative:* Storage grows with each uploaded version, requiring retention/archival policies over time.


---

## ADR 0010: Dynamic Tabular Ingestion & JSONField Persistence for DataRecord

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Users upload arbitrary tabular datasets (CSV, XLSX) containing disparate, organization-specific columns (`ФИО`, `Номер паспорта`, `Дата приказа`, `Department`, `Salary`, etc.). Creating dynamic SQL tables or altering database schemas at runtime for every uploaded file causes schema locking, migration bloat, and security hazards (SQL injection).
- **Decision:**
  We adopt a semi-structured storage model using PostgreSQL's native `JSONField` (backed by `jsonb`) in the `DataRecord` model. Each dataset consists of a parent `DataSource` and a set of `DataRecord` rows indexed by `(data_source, row_number)`. Each record stores a dynamic dictionary `{"column_name": "value"}`.
- **Consequences:**
  - *Positive:*
    1. Complete schema flexibility: arbitrary column names, Russian/Cyrillic headers, and changing schemas are supported out-of-the-box.
    2. Zero DDL/migration overhead: uploading new spreadsheets never requires database schema changes.
    3. Direct mapping to Jinja2 context: `DataRecord.data` maps 1:1 to template context variables during generation.
    4. Fast batch ingestion: using `DataRecord.objects.bulk_create(batch_size=1000)` allows inserting tens of thousands of rows within seconds.
  - *Negative:*
    1. Does not enforce strict SQL-level column types across rows in the same dataset; type coercion and normalization are handled in application services.

---

## ADR 0011: Streaming XLSX & Robust CSV Delimiter/Encoding Autodetection

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Tabular files originate from disparate sources (Russian 1C exports with Windows-1251 or semicolons, UTF-8 with BOM from modern Excel, standard comma-separated RFC 4180 CSVs, and multi-sheet Excel workbooks). Loading large spreadsheets entirely into memory via DOM-based XML parsers risks Out-Of-Memory (OOM) crashes.
- **Decision:**
  1. **CSV:** We use Python standard library `csv` with `utf-8-sig` decoding (seamlessly handling both standard UTF-8 and UTF-8 with BOM, with fallback to `cp1251`). Delimiters (`,`, `;`, `\t`, `|`) are auto-detected via `csv.Sniffer` and frequency fallback.
  2. **XLSX:** We use `openpyxl` exclusively in streaming mode (`read_only=True, data_only=True`), supporting sheet selection and evaluating formula values without expanding the full DOM into memory.
  3. **Strict Validation:** Files must contain valid, non-empty, and non-duplicate headers. Rows with extra unexpected columns trigger explicit errors rather than silently losing data.
- **Consequences:**
  - *Positive:* Robust handling of legacy Russian business exports; protection against memory bloat and zip-bombs; zero silent row loss.

---

## ADR 0012: Relational Mapping Architecture and Pre-Generation Validation Pipeline

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  Binding DOCX template variables to data source columns requires persistence, user edits, and validation. Storing rules as a plain unconstrained JSON blob makes database-level referential integrity and uniqueness checks difficult, while allowing silent misconfigurations.
- **Decision:**
  We adopt a relational model: `MappingConfig` (parent linking `Template` and `DataSource`) and `MappingRule` (child rows specifying `template_variable`, `source_column`, `default_value`, and `required` flag) with a unique constraint on `(mapping_config, template_variable)`. Before generation, `MappingValidationService` executes two-tier validation:
  1. *Configuration tier:* ensures the template is active, dataset is ready, and all template placeholders are mapped or have defaults.
  2. *Record tier:* checks individual row values against required constraints and injects secure system variables (`current_date`, `current_datetime`).
- **Consequences:**
  - *Positive:* Strict relational constraints, granular rule editing, pre-generation failure prevention, and separation between configuration flaws and row-level data flaws.

---

## ADR 0013: Synchronous Document Generation with Granular Error Isolation and Automated ZIP Archival

- **Status:** Accepted
- **Date:** 2026-11-22
- **Context:**
  When generating dozens or hundreds of documents from a spreadsheet, a single corrupted row or missing required field should not crash the entire batch. Users need both individual DOCX documents and a bundled download.
- **Decision:**
  We implement synchronous batch execution in `DocumentGenerationService` with per-record error isolation:
  1. Each selected `DataRecord` is processed independently. A failure in one record records a `GeneratedDocument` with status `FAILED` and detailed diagnostics, allowing the remaining records to proceed.
  2. Successfully generated DOCX files are named using sanitized, predictable schemes (`<slug>_rec<row>_<identifier>.docx`) and saved to storage.
  3. When at least one document succeeds, the batch automatically compiles an in-memory ZIP archive of all successful DOCX files and attaches it to `GenerationBatch.output_file`.
- **Consequences:**
  - *Positive:* High resilience against dirty data; immediate ZIP download; full auditability of failed rows; avoids heavy asynchronous infrastructure (Celery/Redis) during the current phase.
