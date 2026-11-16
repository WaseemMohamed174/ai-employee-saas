"""Database queries package — one module per logical entity group.

Per CODE_RULES 6.3: every query written once, multi-step writes inside a transaction.
The backend imports from here via `from database.queries.users import ...`.
"""
