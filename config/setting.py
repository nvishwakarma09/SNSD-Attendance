import os

class Settings:
    PROJECT_NAME: str = "SNSD Attendance System API"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./attendance.db"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "snm.attendance.123")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

settings = Settings()