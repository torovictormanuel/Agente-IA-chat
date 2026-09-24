# api/index.py — Entry point para Vercel (re-exporta la app ASGI real)
from agent.main import app

__all__ = ["app"]
