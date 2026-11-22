# Architectural Rules & Engineering Guidelines for AI Agents and Contributors

This document establishes strict architectural boundaries, coding standards, and design invariants for any AI agent or software engineer contributing to the **Flowdow** repository.

---

## 1. Core Architectural Invariants

### 1.1 Modular Monolith Boundary Rules
1. The codebase is organized as domain modules in `apps/`.
2. Every module must be cohesive and self-contained:
   - `models.py`: Domain entity definitions and ORM mappings.
   - `services.py`: **All business operations, transformations, validations, and workflow orchestrations.**
   - `views.py`: **Thin controllers** responsible solely for HTTP handling, parameter extraction, service invocation, and response generation.
   - `forms.py`: Request input validation and presentation forms.
   - `urls.py`: Module routing endpoints.
3. Direct cross-module model mutations are prohibited. Modules interact via public service functions or well-defined domain events.
4. Avoid circular imports between apps. If two modules require shared concepts, place those shared concepts in `apps/core/`.

### 1.2 The Service Layer Rule (Strict)
> **Views MUST NOT contain business logic.**

- **DO NOT** perform raw data manipulation, file rendering, or complex database transactions inside view functions or view methods.
- **DO NOT** execute docxtpl or openpyxl parsing inside views.
- **DO** write stateless or instance-based service classes/functions in `apps/<module>/services.py`.
- **DO** keep view methods short (ideally under 25 lines of code):
  ```python
  # CORRECT:
  class GenerateDocumentView(LoginRequiredMixin, View):
      def post(self, request, pk):
          form = GenerationForm(request.POST)
          if not form.is_valid():
              return render(request, "generation/form.html", {"form": form})
          
          batch = DocumentGenerationService.start_batch(
              template_id=pk,
              data_source_id=form.cleaned_data["data_source_id"],
              user=request.user,
          )
          messages.success(request, f"Batch #{batch.id} initiated.")
          return redirect("generation:detail", pk=batch.id)
  ```

---

## 2. Python & Code Quality Standards

1. **Python Version:** Python 3.12+ features are encouraged (pattern matching, improved typing, pipe union operators `int | str`).
2. **Type Hints:** Add type annotations to all service function signatures, parameters, and return values. Type hints improve maintainability and editor completion.
3. **Formatting & Linting:** Code must strictly pass `ruff check` and `ruff format`. Run:
   ```bash
   ruff check .
   ruff format --check .
   ```
4. **No Giant Files:** Keep individual source files focused. If a file approaches 300+ lines, decompose it into smaller sub-modules (e.g. `services/parsing.py`, `services/rendering.py`).
5. **KISS Principle:** Do not add speculative abstractions, metaclasses, or microservice infrastructure until concrete requirements demand them.

---

## 3. Django & Database Rules

1. **Custom User Model:** Always use `accounts.User` (`settings.AUTH_USER_MODEL`). Never import `django.contrib.auth.models.User` directly. Use `get_user_model()` or reference `settings.AUTH_USER_MODEL`.
2. **Timestamped Models:** All domain entities that represent persistable state should inherit from `apps.core.models.TimeStampedModel`.
3. **ORM Integrity:**
   - Always use Django ORM and parameterization. Never assemble raw unparameterized SQL queries.
   - Wrap multi-table mutation flows inside `transaction.atomic()`.
   - Provide `verbose_name` and `verbose_name_plural` for all models.
4. **Migrations:** Every schema change must include a new migration. Never edit already applied migrations if they have been distributed.

---

## 4. Security & Configuration Invariants

1. **Zero Secret Leaks:**
   - Never commit API keys, database passwords, secret keys, or credentials into Git.
   - Use `.env` with `python-dotenv` for local configuration.
   - Provide defaults in `config/settings.py` only for development conveniences, never production credentials.
2. **File Upload Safety:**
   - Only accept permitted extensions (`.docx`, `.csv`, `.xlsx`).
   - Validate uploaded files before passing them to parsing libraries.
   - Use secure file storage paths with unique filenames (UUID or timestamp prefixes) to avoid collisions and directory traversal attacks.

---

## 5. Testing Requirements

1. **Test Runner:** All automated tests must run and pass under `pytest`.
2. **Coverage Areas:**
   - Service Layer: Test business operations, edge cases, and validation rules.
   - Model Layer: Test custom methods, properties, and constraints.
   - Presentation Layer: Test view access permissions (`@login_required`), form handling, and HTTP status codes.
3. Use `pytest-django` fixtures (`db`, `client`, `rf`) for clean and isolated test runs.

