import os

class Config:
    # Flask Core
    SECRET_KEY = os.environ.get("SECRET_KEY", "fallback_secret_key")
    
    # Database - requires DATABASE_URL in .env
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/help_db?sslmode=disable"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
    }
    
    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "helpdesk_secret_key_2026")
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour in seconds
    
    # Email Configuration
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ["true", "on", "1"]
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "helpdesk@example.com")
    MAIL_API_KEY = os.environ.get("MAIL_API_KEY", "")
    
    # OpenRouter AI Configuration
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    OPENROUTER_FALLBACK_MODELS = os.environ.get(
        "OPENROUTER_FALLBACK_MODELS",
        "deepseek/deepseek-r1:free,google/gemma-4-31b-it:free"
    )
    OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "http://localhost:5000")
    OPENROUTER_APP_NAME = os.environ.get("OPENROUTER_APP_NAME", "HelpDesk AI")
    OPENROUTER_TIMEOUT = int(os.environ.get("OPENROUTER_TIMEOUT", "60"))
    
    # File Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
