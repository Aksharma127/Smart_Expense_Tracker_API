"""API routes package.

Exposes the FastAPI router instances for registration in the app factory.
"""

from src.api.routes import expenses, health

__all__ = ["expenses", "health"]
