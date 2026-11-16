"""AI adapter layer — provider selection + generation (FR-19).

Public entry point: `adapter.generate(...)` returning an AiResponse.
Providers: mock (sandbox, no key needed), gemini (default), openai, anthropic.
The provider with a key in settings/.env wins automatically; mock is the fallback.
"""
from backend.services.ai.adapter import AiResponse, get_adapter

__all__ = ["AiResponse", "get_adapter"]
