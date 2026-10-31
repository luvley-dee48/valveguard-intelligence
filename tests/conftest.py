import os
import secrets
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["GEMINI_API_KEY"] = ""   # tests must never call the real Gemini

import pytest


@pytest.fixture(autouse=True)
def fresh_db():
    from app.db import Base, engine
    from app import auth, system
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    auth._attempts.clear()
    system.REQUESTS.clear()
    yield