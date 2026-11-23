# Flowdow Demo & Sample Files

This directory provides pre-configured sample files allowing you to test Flowdow's complete document automation pipeline in under 60 seconds.

---

## 📁 Included Files

1. **`sample_certificate.docx`**
   - A standard Certificate of Employment template containing template placeholders:
     - `{{ full_name }}`
     - `{{ position }}`
     - `{{ department }}`
     - `{{ salary }}`
     - `{{ current_date }}` (system variable)

2. **`sample_employees.csv`**
   - A UTF-8 (with BOM) comma-separated spreadsheet containing 5 employee records:
     - Columns: `ФИО`, `Должность`, `Отдел`, `Оклад`

3. **`sample_employees.xlsx`**
   - Microsoft Excel workbook matching the employee records from the CSV file.

---

## ⚡ 60-Second Walkthrough Guide

Ensure Flowdow is running (e.g. via `docker compose up -d` with Docker Desktop running), then open **http://localhost:8000**:

1. **Log in:**
   - Sign in using your administrator or editor account.

2. **Create a Document Type:**
   - Navigate to **Document Types** -> **New Document Type**.
   - Name: `Справка с места работы` (or `Employment Certificate`).
   - Click **Save**.

3. **Upload Template:**
   - In the document type view, click **Upload Template**.
   - Name: `Шаблон справки 2026`.
   - File: Select `examples/sample_certificate.docx`.
   - Notice that Flowdow automatically extracts variables:
     `full_name`, `position`, `department`, `salary`, `current_date`.
   - Set status to **Active**.

4. **Upload Data Source:**
   - Navigate to **Data Sources** -> **Import Data Source**.
   - Select either `examples/sample_employees.csv` or `examples/sample_employees.xlsx`.
   - Name: `Штат сотрудников 2026`.
   - Click **Upload & Ingest**. Review the parsed tabular data preview.

5. **Create Mapping Configuration:**
   - Navigate to **Mappings** -> **Create Mapping**.
   - Select your Template and Data Source.
   - Map template variables:
     - `full_name` ➔ `ФИО` (Required)
     - `position` ➔ `Должность` (Required)
     - `department` ➔ `Отдел`
     - `salary` ➔ `Оклад`
     - `current_date` ➔ `_system:current_date` (Auto-filled with today's date)
   - Click **Save & Validate**.

6. **Generate Documents:**
   - Navigate to **Generate** -> **New Generation Batch**.
   - Select your Mapping Configuration.
   - Choose **Generate for All Records** (or select specific rows).
   - Click **Start Generation**.

7. **Download Result:**
   - Download the generated ZIP package containing 5 individually personalized DOCX certificates, or download individual documents directly.
   - View the execution audit record in **History**.

