from fastapi import FastAPI

from main import app


def test_app_instance() -> None:
    assert isinstance(app, FastAPI)
