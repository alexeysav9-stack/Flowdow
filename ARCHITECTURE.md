# Flowdow Architecture Specification

**Architecture Pattern:** Modular Monolith  
**Application Type:** Self-Hosted Web Application  
**Primary Language & Runtime:** Python 3.12+ / CPython  
**Framework:** Django 5.1  
**Database:** PostgreSQL 16+ (via `psycopg` 3)  
**Frontend Stack:** Django Templates, Bootstrap 5.3, Bootstrap Icons, Native Vanilla JS  

---

## 1. Architectural Principles

1. **Modular Monolith:** Flowdow is organized as a collection of cohesive, loosely-coupled domain modules located in `apps/`. Each module encapsulates its own data models, services, forms, and views.
2. **Explicit Layer Separation:**
   - **Presentation Layer:** Views, Forms, Context Processors, HTML Templates. Views handle HTTP transport only (request validation, calling services, HTTP responses/redirects).
   - **Application / Service Layer:** Services located in `apps/<module>/services.py`. All business operations, domain calculations, workflows, and transactional logic live here.
   - **Domain / Business Layer:** Django ORM Models and Managers encapsulating field constraints, relationships, and queries.
   - **Infrastructure Layer:** Database access (ORM), File storage (Media storage), Document processing engine (DOCX/XLSX libraries).
3. **No Business Logic in Views:** Views must never manipulate models directly for complex domain operations; they delegate to service functions or classes.
4. **Single-Tenant Deployment Model:** Each deployment instance serves one organization. This avoids premature multi-tenant complexity (row-level tenancy filtering, schema isolation) while guaranteeing absolute physical data separation for security-conscious self-hosters.
5. **Keep It Simple & Robust (KISS):** Avoid artificial layers, unnecessary microservices, Celery, or frontend build toolchains in the foundation stage.

---

## 2. System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                                  USER BROWSER                                     |
|                       (HTML5 + Bootstrap 5 + Vanilla JS)                          |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          | HTTP / HTTPS
                                          v
+-----------------------------------------------------------------------------------+
|                                PRESENTATION LAYER                                 |
|   +-------------------+  +--------------------+  +----------------------------+   |
|   |   Django Views    |  |    Django Forms    |  |  Django Templates Context  |   |
|   +---------+---------+  +---------+----------+  +-------------+--------------+   |
+-------------|----------------------|---------------------------|------------------+
              |                      |                           |
              v                      v                           v
+-----------------------------------------------------------------------------------+
|                        APPLICATION / SERVICE LAYER                                |
|   apps/core/services.py             - Dashboard & Analytics Service               |
|   apps/accounts/services.py         - User Management & Authentication Service    |
|   apps/organizations/services.py    - Organization & Settings Service             |
|   apps/documents/services.py        - Document Type & Metadata Catalog Service    |
|   apps/templates_manager/services.py- Template Inspection & Variable Service     |
|   apps/data_sources/services.py     - CSV / XLSX Data Ingestion Service           |
|   apps/mapping/services.py          - Variable-to-Column Mapping & Validation     |
|   apps/generation/services.py       - Document Rendering & Batch Packing Service  |
|   apps/audit/services.py            - System Audit Log Service                    |
+-------------------------------------+---------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------------+
|                          DOMAIN / BUSINESS LAYER                                  |
|   Models: User, Organization, DocumentType, DocumentTemplate, DataSource,        |
|           FieldMappingSchema, GenerationBatch, AuditLog                           |
+-------------------------------------+---------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------------+
|                            INFRASTRUCTURE LAYER                                   |
|   +-----------------------+  +----------------------+  +----------------------+   |
|   | PostgreSQL 16 (ORM)   |  | Local / Volume Media |  | docxtpl / openpyxl   |   |
|   +-----------------------+  +----------------------+  +----------------------+   |
+-----------------------------------------------------------------------------------+
```

---

## 3. Directory Layout & Module Structure

```
Flowdow/
├── config/                     # Project configuration & settings
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py             # Environment-driven Django settings
│   ├── urls.py                 # Root URL routing table
│   └── wsgi.py
├── apps/                       # Modular Monolith applications
│   ├── core/                   # Shared base models, dashboard & selectors
│   ├── accounts/               # Custom User, authentication, profile
│   ├── organizations/          # Single-tenant organization settings
│   ├── documents/              # Document types catalog
│   ├── templates_manager/      # DOCX template upload & placeholder analysis
│   ├── data_sources/           # CSV / XLSX tabular data ingestion
│   ├── mapping/                # Schema linking placeholders to dataset headers
│   ├── generation/             # Single & batch document generation engine
│   └── audit/                  # Audit trail logging for actions
├── templates/                  # Server-rendered HTML templates (Bootstrap 5)
│   ├── base.html
│   ├── components/
│   │   ├── navbar.html
│   │   ├── sidebar.html
│   │   └── messages.html
│   ├── core/
│   ├── accounts/
│   ├── organizations/
│   ├── documents/
│   ├── templates_manager/
│   ├── data_sources/
│   └── generation/
├── static/                     # Assets (CSS, JS)
│   ├── css/
│   │   └── app.css
│   └── js/
│       └── app.js
├── tests/                      # Automated test suite (pytest-django)
│   ├── conftest.py
│   ├── test_core/
│   ├── test_accounts/
│   ├── test_organizations/
│   └── test_modules/
├── Dockerfile                  # Application container definition
├── docker-compose.yml          # Postgres + Web service composition
├── pyproject.toml              # Dependencies, ruff & pytest configurations
├── .env.example                # Sample environment variables
└── manage.py                   # Django CLI utility
```

---

## 4. Module Responsibilities & Contracts

### 4.1 `apps.core`
- **Models:** `TimeStampedModel` (abstract base model with `created_at` and `updated_at`).
- **Services:** `DashboardMetricsService` (aggregates system metrics for the dashboard).
- **Views:** `DashboardView`, `HealthCheckView`.
- **Context Processors:** Global layout data (workspace name, user permissions).

### 4.2 `apps.accounts`
- **Models:** `User` (inherits `AbstractUser`). Pre-configured before first migration to eliminate future migration hazards.
- **Services:** `UserService` (creation, credential management, profile updates).
- **Views:** `LoginView`, `LogoutView`, `ProfileView`.

### 4.3 `apps.organizations`
- **Models:** `Organization` (name, registration number, contact info, settings).
- **Services:** `OrganizationService` (get or create default organization, update settings).
- **Views:** `OrganizationSettingsView`.

### 4.4 `apps.documents`
- **Models:** `DocumentType` (name, slug, description, is_active, active_template, total_templates).
- **Services:** `DocumentTypeService` (taxonomy CRUD, validation, prefetching), `DocumentManagementPermissionMixin` (role-based modification checks).
- **Views:** `DocumentListView`, `DocumentTypeCreateView`, `DocumentTypeDetailView`.

### 4.5 `apps.templates_manager`
- **Models:** `Template` (document_type FK, name, file with collision-free upload path, version integer, status [draft, active, archived], detected_variables JSON list). Aliased as `DocumentTemplate` for backward compatibility.
- **Services:**
  - `DocxSecurityValidator`: verifies file size (max 10MB), `.docx` extension, `PK\x03\x04` magic bytes, OpenXML ZIP integrity (`word/document.xml`), and decompression bomb prevention.
  - `TemplateInspectionService`: inspects DOCX XML runs via `docxtpl`, merges fragmented text runs, extracts unique undeclared Jinja2 variables without executing code, and filters valid Python identifiers.
  - `TemplateService`: handles automatic version incrementing (`v1, v2...`), safe file storage namespacing (`v{version}_{token}_{slug}.docx`), activation, and archival lifecycle transitions.
- **Views:** `TemplateListView`, `TemplateUploadView`, `TemplateActivateView`, `TemplateArchiveView`, `TemplateDownloadView`.

### 4.6 `apps.data_sources`
- **Models:**
  - `DataSource`: stores dataset metadata (`name`, `file` via secure collision-free path, `format` [CSV/XLSX], `status` [pending/processing/ready/error], `sheet_name`, `headers` JSON list, `row_count`, `column_count`, `error_message`, `uploaded_by`).
  - `DataRecord`: dynamic tabular record (`data_source` FK with CASCADE, `row_number`, `data` JSONField holding arbitrary column-value pairs). Unique constraint and index on `(data_source, row_number)`.
- **Services:**
  - `DataSourceSecurityValidator`: validates file size (<= 20MB), extension (`.csv`, `.xlsx`), binary null byte detection in CSV, ZIP OpenXML structure in XLSX, zip-bomb ratio checks, and forbids executable payloads.
  - `CsvImportService`: decodes text via `utf-8-sig` (transparently supporting UTF-8 and UTF-8 with BOM), autodetects delimiters (`,`, `;`, `\t`, `|`), skips blank lines, validates non-empty & unique headers, validates row cell counts without silent data loss.
  - `XlsxImportService`: streams Excel sheets using `openpyxl` with `read_only=True` and `data_only=True`, supports sheet selection, trims trailing whitespace, normalizes dates/datetimes/floats/booleans, and enforces resource safety.
  - `DataSourceService`: handles creation, batch bulk-insertion of `DataRecord` rows (chunks of 1,000), error diagnostics recording, paginated previewing, safe cascading deletion (including disk file cleanup), and audit logging.
- **Views:** `DataSourceListView`, `DataSourceUploadView`, `DataSourceDetailView`, `DataSourceDeleteView`, `DataSourceDownloadView`.

### 4.7 `apps.mapping`
- **Models:** `FieldMappingSchema` (links `DocumentTemplate` to `DataSource`), `FieldMappingItem` (variable name, column header, default value, required flag).
- **Services:** `MappingValidationService` (verifies all template variables have matched columns or defaults).
- **Views:** `MappingListView`, `MappingConfigView`.

### 4.8 `apps.generation`
- **Models:** `GenerationBatch` (template, data source, user, status, total records, successful records, output archive path).
- **Services:** `DocumentGenerationService` (processes rows, renders docxtpl context, writes output DOCX / ZIP).
- **Views:** `GenerationHistoryView`, `GenerationDetailView`.

### 4.9 `apps.audit`
- **Models:** `AuditLog` (user, action, target model, object id, ip address, extra JSON payload).
- **Services:** `AuditService` (records system actions cleanly).

---

## 5. Security & Data Protection

1. **Authentication & Authorization:** Standard Django session authentication with PBKDF2 / Argon2 password hashing. Strict `@login_required` decorators on all business views.
2. **File Upload Security:** Uploaded DOCX, CSV, and XLSX files are validated against allowed extensions and MIME types. Files are stored in designated `MEDIA_ROOT` directories with sanitized filenames.
3. **Template Sandbox:** Jinja2 environment in `docxtpl` is restricted from executing arbitrary Python commands or system calls.
4. **Environment Secrets:** No passwords, database credentials, or secret keys are stored in version control. All configuration is read via `.env` with fallback defaults for local development.

---

## 6. Database Strategy

- **DBMS:** PostgreSQL 16+ using the official `psycopg` 3 driver (`django.db.backends.postgresql`).
- **Connection pooling & Transactions:** Standard transactional blocks (`transaction.atomic()`) inside service methods to guarantee data integrity across multi-model operations.
- **Migration Strategy:** All schema changes must be represented by deterministic Django migrations in `apps/<module>/migrations/`.

