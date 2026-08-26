import logging

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from src.database import engine, Base
from src.routers import auth_router, employee_router, attendance_router, unit_router, user_router, role_router, database_router
from config.setting import settings

logger = logging.getLogger(__name__)

# Create database tables if they don't exist
Base.metadata.create_all(bind=engine)

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for scanning QR codes and managing team attendance.",
    version="1.0.0"
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# Include separated routers
app.include_router(auth_router)
app.include_router(employee_router)
app.include_router(attendance_router)
app.include_router(unit_router)
app.include_router(user_router)
app.include_router(role_router)
app.include_router(database_router)

@app.get("/")
def root():
    return {"message": "Attendance API is running. Visit /docs for Swagger UI."} 

