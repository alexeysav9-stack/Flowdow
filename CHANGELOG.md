# Changelog

All notable changes to **Flowdow** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-22

### Initial MVP Open-Source Release

#### Added
- **Core Architecture & Foundation:**
  - Modular monolith architecture organized under `apps/` (`core`, `accounts`, `organizations`, `documents`, `templates_manager`, `data_sources`, `mapping`, `generation`, `audit`).
  - Custom User model (`accounts.User`) with role-based access control (`admin`, `editor`, `viewer`).
  - Strict Service Layer separation (business operations isolated from HTTP views).
  - Modern responsive UI built on Bootstrap 5.3, Bootstrap Icons, and server-rendered Django templates.
  - Full internationalization support with Russian (RU) and English (EN) language switching.
  - Health check endpoint (`/health/`) monitoring application and database connectivity.

- **Document Types & Template Management:**
  - `DocumentType` catalog with auto-generated slugs.
  - `Template` entity with auto-incrementing version control (`v1`, `v2`, ...) and lifecycle statuses (`draft`, `active`, `archived`).
  - Collision-proof file storage preventing overwrite of historical template revisions.
  - Deep DOCX placeholder inspection via AST analysis (`docxtpl`), resolving Word's split XML runs.
  - OpenXML ZIP validation defending against malicious files, zip bombs, and path traversal.

- **Data Sources & Tabular Ingestion:**
  - Ingestion engine for CSV and XLSX files.
  - CSV parser supporting UTF-8, UTF-8 with BOM, and Windows-1251 fallback with auto-delimiter detection (`,`, `;`, `\t`, `|`).
  - Memory-efficient streaming XLSX reader (`openpyxl` with `read_only=True`) supporting multi-sheet selection and typed formatting.
  - Dynamic record storage via PostgreSQL `jsonb` (`DataRecord.data`).
  - Comprehensive safety limits: 20MB file limit, 50,000 rows, 200 columns.

- **Variable Mapping & Pre-Flight Validation:**
  - `MappingConfig` and `MappingRule` pairing template variables to spreadsheet columns.
  - Configurable fallback default values and mandatory field flags.
  - Built-in safe system variables (`current_date`, `current_datetime`, `current_year`, `system_platform`).
  - Two-stage validation: configuration readiness check and individual record pre-flight inspection.

- **Document Generation & Packaging:**
  - Single document generation from chosen records.
  - Bulk batch generation (`GenerationBatch`) with sanitized output filenames.
  - Row-level error isolation: failures on individual rows do not disrupt remaining documents in a batch.
  - Automated ZIP archive generation packaging all rendered DOCX files in a batch.
  - Generation audit trail recording status, success rates, duration, and error diagnostics.

- **DevOps, Docker & CI:**
  - Production-ready `Dockerfile` and `docker-compose.yml` with PostgreSQL 16.
  - Zero-secret `.env.example` template.
  - GitHub Actions CI pipeline testing code quality (`ruff check`, `ruff format`) and test suite (`pytest`) on Python 3.12.
  - Ready-to-use sample files and 60-second walkthrough in `examples/`.

