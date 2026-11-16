"""Backend package for AI Employee (shop-assistant).

Structure (per CODE_RULES 6.2):
- main.py: FastAPI entry point (app)
- api/: routes only (no business logic)
- services/: business logic
- schemas/: Pydantic validation of inputs and outputs
- core/: settings, security, errors, logging
- shared/: shared helpers and constants
"""
