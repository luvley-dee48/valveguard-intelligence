"""Runtime configuration. Reads environment variables and an optional .env file."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #")[0]
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# Values that have been published (in .env.example or old commits). Tokens signed with
# them can be forged by anyone, so the server refuses to start with one.
_PUBLIC_SECRETS = {"change-me-to-a-long-random-string", "change-me", "secret", "changeme"}


def _secret_key() -> str:
    """Use SECRET_KEY if set, otherwise create one once and keep it on disk."""
    env = os.getenv("SECRET_KEY", "").strip()
    if env:
        if env in _PUBLIC_SECRETS or len(env) < 16:
            raise RuntimeError(
                "SECRET_KEY is a placeholder or too short. Leave it empty in .env to auto-generate one, "
                "or set it to the output of: python -c \"import secrets;print(secrets.token_urlsafe(48))\"")
        return env
    key_file = BASE_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return key


SECRET_KEY = _secret_key()
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "12"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'valveguard.db'}")

# Gemini API. Leave the key empty to run on the rule-based fallback.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-4-26b-a4b-it")
AI_CALLS_PER_HOUR = int(os.getenv("AI_CALLS_PER_HOUR", "30"))

# Google sign-in: the OAuth 2.0 *Web* client ID from Google Cloud Console. Empty disables it.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "") or os.getenv("VITE_GOOGLE_CLIENT_ID", "")

# Free plan limits (shown on the pricing page).
FREE_VALVE_LIMIT = int(os.getenv("FREE_VALVE_LIMIT", "25"))
FREE_REPORTS_PER_MONTH = int(os.getenv("FREE_REPORTS_PER_MONTH", "50"))

# The React frontend runs on another origin (Vite dev server locally, Lovable in production).
_DEFAULT_ORIGINS = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]
# Lovable preview and published URLs. Auth is a bearer token (not a cookie), so CORS only
# controls which sites can call the API from a browser; it is not the security boundary.
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"https://[a-z0-9-]+\.(lovable\.app|lovableproject\.com)") or None
