# Contributing to Flowdow

Thank you for your interest in contributing to **Flowdow**! We welcome community contributions, bug reports, and feature proposals.

---

## 1. Architectural Guidelines & Boundaries

Before writing code, please review [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

Key architectural invariants to maintain:
- **Modular Monolith:** Domain applications live under `apps/` (`documents`, `templates_manager`, `data_sources`, `mapping`, `generation`, `audit`).
- **Strict Service Layer:** Views must remain thin HTTP controllers (under ~25 lines). Business operations, file parsing, and data validation belong exclusively to `services.py`.
- **Type Annotations:** All public service functions, methods, and helpers must include Python 3.12+ type hints.
- **Custom User Model:** Always reference `settings.AUTH_USER_MODEL` or `get_user_model()`. Never import `django.contrib.auth.models.User` directly.
- **Security First:** Never disable CSRF protection. Always validate file headers/magic bytes before parsing. Sanitize all filenames before disk storage or downloads.

---

## 2. Development Setup

### Prerequisites
- Python 3.12+
- PostgreSQL 16+ (or SQLite for fast isolated testing)
- `uv` (recommended) or `pip` / `venv`
- Docker & Docker Compose (optional for local multi-container dev)

### Getting Started

```bash
# 1. Clone your fork
git clone https://github.com/<your-username>/flowdow.git
cd flowdow

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies in editable mode with development tools
pip install -e ".[dev]"

# 4. Configure local environment
cp .env.example .env

# 5. Apply migrations
python manage.py migrate

# 6. Run test suite to verify setup
pytest
```

---

## 3. Code Quality & Standards

Flowdow enforces strict linting and formatting via **Ruff**:

```bash
# Check code style & linting rules
ruff check .

# Check formatting
ruff format --check .

# Automatically apply fixes and format code
ruff check --fix .
ruff format .
```

---

## 4. Testing Requirements

- All pull requests must include automated tests in `tests/`.
- Tests must pass cleanly with `pytest`:
  ```bash
  pytest
  ```
- Coverage expectations:
  - **Services:** Test all business logic paths, edge cases, and validation rules.
  - **Models:** Test model constraints, string representations, and auto-generated fields.
  - **Views:** Test authorization (`LoginRequiredMixin`), permission controls, form validation, and HTTP responses.

---

## 5. Pull Request Process

1. Fork the repository and create a descriptive branch:
   ```bash
   git checkout -b feat/add-excel-multi-sheet
   ```
2. Implement your changes adhering to [AGENTS.md](AGENTS.md).
3. Ensure all tests pass (`pytest`) and Ruff checks succeed (`ruff check . && ruff format --check .`).
4. If your change alters database schemas, include a new Django migration. Never modify already committed migrations.
5. Submit a pull request to `main` with a clear description of the problem solved and test coverage added.

