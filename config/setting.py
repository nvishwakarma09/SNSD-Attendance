import os

class Settings:
    PROJECT_NAME: str = "SNSD Attendance System API"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./attendance.db"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "snm.attendance.123")
    DATABASE_RESET_ENABLED: bool = os.getenv("DATABASE_RESET_ENABLED", "false").lower() == "true"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

settings = Settings()