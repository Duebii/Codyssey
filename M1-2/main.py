"""Run from M1-2: python -m uvicorn main:app --reload."""

from app.main import create_app

app = create_app()
