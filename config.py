"""
config.py — Application Configuration

This is where all the app settings live. Keeping them in one place
makes it easy to swap between development and production without
hunting through 10 different files.
"""

import os

# Base directory of the project — handy for building absolute paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """
    Base configuration class. All environments inherit from this.
    Override specific values in subclasses below.
    """

    # Secret key for session signing — in production, this should come
    # from an environment variable, NOT be hardcoded like this.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")

    # SQLite database stored right next to our code for simplicity.
    # For production you'd swap this out for PostgreSQL or MySQL.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'inventory.db')}"
    )

    # SQLAlchemy doesn't need to track every model modification — it just
    # adds overhead and prints annoying warnings if set to True.
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pretty-print JSON responses so they're readable in the browser/Postman
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    """Development settings — verbose errors, debug mode on."""
    DEBUG = True


class ProductionConfig(Config):
    """Production settings — errors are logged, not shown to users."""
    DEBUG = False


# Map string names to config classes — makes it easy to pick one via env var
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

# Which config to actually use — defaults to development
ActiveConfig = config_map.get(os.environ.get("FLASK_ENV", "default"), DevelopmentConfig)
