import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    """Tiny .env loader so we don't need python-dotenv as a hard dependency."""
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
                    value = value[1:-1]
                os.environ.setdefault(key, value)


_load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-please")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "skillgappath.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # YouTube Data API v3 key (optional, free quota). Leave blank to use the
    # built-in verified flagship videos + creator search links instead of
    # live per-topic search.
    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

    # Firebase Web SDK configuration. These values are safe to expose to the browser.
    FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "")
    FIREBASE_AUTH_DOMAIN = os.environ.get("FIREBASE_AUTH_DOMAIN", "")
    FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "")
    FIREBASE_STORAGE_BUCKET = os.environ.get("FIREBASE_STORAGE_BUCKET", "")
    FIREBASE_MESSAGING_SENDER_ID = os.environ.get("FIREBASE_MESSAGING_SENDER_ID", "")
    FIREBASE_APP_ID = os.environ.get("FIREBASE_APP_ID", "")

    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")
