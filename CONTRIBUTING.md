# Contributing

KnowledgeForge is both a useful local-first product and a hands-on exploration of secure AI orchestration. Contributions should preserve that dual purpose: improve the user’s ability to develop ideas while keeping data flow, model behavior, and trust boundaries inspectable.

1. Create a branch from the default branch.
2. Never use real private recordings in fixtures or issues.
3. Install development dependencies with `python -m pip install -e ".[dev]"`.
4. Run `ruff check .` and `pytest`.
5. Keep modules focused and document operationally surprising behavior, especially cloud-file, privacy, and lifecycle decisions.
6. Update documentation when configuration or deployment behavior changes.

Pull requests should explain the user-visible change, privacy impact, tests performed, and migration considerations.
