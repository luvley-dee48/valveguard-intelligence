import os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["GEMINI_API_KEY"] = ""
import pytest

@pytest.fixture(autouse=True)
def fresh_db():
    from app.db import Base, engine
    from app import auth
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    auth._attempts.clear()
    yield
