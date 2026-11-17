# Contributing Guidelines

Thank you for your interest in contributing to the **Semantic Data Fabric & Autonomous Analyst** project! We adhere to open-science principles, clean modular engineering, and reproducible data workflows.

## Code Standards
1. **Formatting & Linting:** All Python code must comply with `ruff` rules defined in `pyproject.toml`.
2. **Type Hints:** Use explicit Python type annotations across `src/` modules.
3. **Data Privacy:** Never commit real credentials, `.env` files, or proprietary database dumps. Use synthetic generators in `data/seed/`.
4. **SQL Safety:** Any agentic SQL execution module must enforce read-only transactions (`SELECT` only) unless explicitly approved via the Human-in-the-Loop (HITL) interface.

## Pull Request Process
1. Create a feature branch (`git checkout -b feat/your-feature`).
2. Add corresponding unit tests in `tests/`.
3. Verify tests pass via `pytest`.
4. Submit a clear description detailing the architectural impact.
