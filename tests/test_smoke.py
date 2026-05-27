import os
import sys

from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import app  # noqa: E402


def test_app_instance() -> None:
    assert isinstance(app, FastAPI)
