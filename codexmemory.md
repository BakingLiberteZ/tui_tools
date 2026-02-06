# Project Guidelines

## Python Environment

- Package manager: use `uv` for all Python management (dependencies, virtual environments, and running scripts).
- Never use `pip` directly; use `uv pip` or `uv run`.
- Preferred sync flow: `uv sync --dev`.

## Code Quality

### Formatting and Linting

- Use `ruff` for both linting and formatting.
- Run before committing:
  - `uv run ruff check . --fix`
  - `uv run ruff format .`

### Type Checking

- Use `ty` for type verification.
- Recommended especially for LLM-generated code to catch subtle issues.
- Run:
  - `uv run ty check`

## Commands Reference

```bash
# Setup
uv venv
uv sync --dev

# Code quality
uv run ruff check . --fix
uv run ruff format .
uv run ty check

# Run app
uv run python -m sassy_wallet
```
