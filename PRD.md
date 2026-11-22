# Product Requirements Document (PRD) — Flowdow

**Version:** 0.1.0  
**Status:** Approved  
**Author:** Software Architecture & Product Engineering Team  

---

## 1. Executive Summary

**Flowdow** is a self-hosted, open-source platform designed to automate document preparation workflows for businesses and organizations. It enables operational teams, legal counsel, HR specialists, and accountants to turn structured tabular data (CSV, XLSX) into finalized DOCX documents using custom templates without writing a single line of code.

Unlike SaaS alternatives that transmit sensitive corporate documents through external cloud infrastructure, Flowdow is fully self-hosted, ensuring complete data residency, air-gapped readiness, and sovereignty.

---

## 2. Problem Statement

Organizations routinely generate repetitive documents:
- HR: Employment contracts, NDAs, offer letters, bonus agreements, termination notices.
- Sales & Procurement: Supply agreements, price quotes, commercial proposals, work acceptance acts.
- Finance & Accounting: Invoices, reconciliation statements, payment guarantees.
- Education & Events: Certificates, accreditations, personalized invitations.

**Current Pain Points:**
1. **Manual Editing:** Employees manually copy-paste names, passport numbers, sums, and dates into Word files, introducing human errors.
2. **Developer Dependency:** Python scripts or mail-merge tools often require technical intervention whenever a template or column changes.
3. **Data Privacy Risks:** Third-party cloud SaaS document generators create compliance risks (GDPR, personal data protection laws).
4. **Fragile Office Plugins:** Built-in Word mail-merge tools lack centralized template governance, data validation, and batch audit trails.

---

## 3. Product Vision & Goals

### 3.1 Vision
Become the default open-source standard for on-premise document automation: simple for non-technical users to configure, robust for system administrators to host, and clean for developers to extend.

### 3.2 Key Product Goals
- **No-Code Configuration:** Non-technical operators must be able to upload a DOCX template, upload a spreadsheet, match fields visually, and generate documents.
- **Data Integrity & Validation:** Validate spreadsheet values against expected types (dates, numbers, currency, required fields) *before* generation.
- **Batch & Single Generation:** Support generating a single document for ad-hoc tasks or thousands of documents packaged into a downloadable ZIP archive.
- **Full Traceability:** Track who generated what, when, using which template and dataset.
- **Self-Hosted Simplicity:** Single command startup via Docker Compose, minimal resource footprint, standard relational database.

---

## 4. User Personas

| Persona | Role | Key Needs |
|---|---|---|
| **Operations / HR / Legal Specialist** | End User | Upload DOCX templates, upload XLSX files, map columns to placeholders, download generated files. |
| **Department Lead / Manager** | Workflow Owner | Manage document types, approve templates, review generation history and audit logs. |
| **System Administrator / DevOps** | Infrastructure | Easy deployment via Docker, PostgreSQL storage, backups, secure user authentication. |

---

## 5. Core Functional Requirements

### 5.1 Document Types & Templates
- Define **Document Types** (e.g., "Employee Agreement", "Contractor Statement").
- Upload and version **DOCX Templates** containing Jinja2-style placeholders (e.g. `{{ employee_name }}`, `{{ salary | format_currency }}`).
- Automatically inspect uploaded templates to discover all required placeholder variables.

### 5.2 Data Source Management
- Upload structured data files in **CSV** and **XLSX** formats.
- Automatically parse headers, row counts, and data sample previews.
- Support dataset re-use across multiple generation runs.

### 5.3 Field Mapping & Validation
- Interactive mapping of template placeholders to data source columns.
- Support default values, type constraints (string, integer, decimal, date), and required flags.
- Real-time pre-flight validation check alerting the user to missing values or incompatible data types.

### 5.4 Document Generation
- Single record preview and generation.
- Batch generation for all rows in a dataset.
- Output formats: Individual DOCX files and compressed ZIP archives.
- Status tracking: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.

### 5.5 Audit & History
- Comprehensive log of every generation batch (user, timestamp, row count, template version, status, duration).
- Audit trail for template uploads, modifications, and configuration changes.

---

## 6. Non-Functional Requirements

- **Architecture:** Modular Monolith with clear boundary encapsulation and dedicated Service Layer.
- **Performance:** Sub-second response time for UI operations; batch document generation throughput of 100+ documents/minute for typical corporate agreements.
- **Security:** CSRF protection, secure session management, salted password hashing, sanitization of uploaded files, strict role-based access.
- **Reliability:** Idempotent generation jobs, transaction safety for database writes, error handling with diagnostic messages.
- **Data Model Scope:** Single-tenant installation per organization for Version 1.0 (no multi-tenant data leaks).

---

## 7. MVP Scope vs Future Horizons

| Capability | MVP (v0.1 - v0.2) | Future Horizon (v1.0+) |
|---|---|---|
| **Multi-tenancy** | Single organization per instance | Multi-organization SaaS support |
| **Templates** | DOCX files with docxtpl/Jinja2 | PPTX, XLSX, HTML templates |
| **Data Sources** | CSV, XLSX uploads | Database connections, Google Sheets, Webhooks |
| **Generation Engine** | Synchronous & service-driven | Celery / Background workers with progress websockets |
| **Output Formats** | DOCX, ZIP | PDF conversion (LibreOffice / Gotenberg), digital signatures |
| **API** | Internal Django views | Public REST API (Django REST Framework) |

