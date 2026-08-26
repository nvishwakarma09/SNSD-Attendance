from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import Literal
import csv
import io
import src.models as models, src.schemas as schemas
from src.database import get_db, reset_database
from src.security import SecurityService, get_current_user, get_user_from_refresh_token, revoke_token
from config.setting import settings
from .services import SewadalService, AttendanceService

# Create distinct routers for clean API grouping
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
employee_router = APIRouter(prefix="/api/sewadals", tags=["Sewadals"])
attendance_router = APIRouter(prefix="/api/attendance", tags=["Attendance"])
unit_router = APIRouter(prefix="/api/units", tags=["Units"])
user_router = APIRouter(prefix="/api/users", tags=["Users"])
role_router = APIRouter(prefix="/api/roles", tags=["Roles"])
database_router = APIRouter(prefix="/api/database", tags=["Database"])


def _parse_query_date(value: str | None, parameter_name: str) -> date | None:
    if value is None:
        return None

    value = value.strip()
    date_formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    )
    for date_format in date_formats:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue

    raise HTTPException(
        status_code=400,
        detail=f"Invalid {parameter_name}. Use a valid date such as 2026-08-24 or 24/08/2026.",
    )

# --- Role Routes ---
@role_router.post("", response_model=schemas.RoleResponse, status_code=201)
def create_role(request: schemas.RoleCreate, db: Session = Depends(get_db)):
    role_name = request.role_name.strip()
    
    if not role_name:
        raise HTTPException(status_code=400, detail="Role name cannot be empty")
    if db.query(models.Role).filter(models.Role.role_name == role_name).first() is not None:
        raise HTTPException(status_code=409, detail="A role with this name already exists")

    role = models.Role(role_name=role_name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

# --- User Routes ---
@user_router.post("", response_model=schemas.UserResponse, status_code=201)
def create_user(request: schemas.UserCreate, db: Session = Depends(get_db)):
    sd_id = request.sd_id.strip()
    email = request.email.strip().lower()
    if not sd_id or not email or not request.password:
        raise HTTPException(status_code=400, detail="sd_id, email, and password are required")

    if db.get(models.Sewadal, sd_id) is None:
        raise HTTPException(status_code=404, detail=f"Sewadal {sd_id} not found")
    if db.get(models.Unit, request.unit_id) is None:
        raise HTTPException(status_code=404, detail=f"Unit {request.unit_id} not found")
    if request.role_id is not None and db.get(models.Role, request.role_id) is None:
        raise HTTPException(status_code=404, detail=f"Role {request.role_id} not found")
    if db.query(models.User).filter(models.User.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    user = models.User(
        sd_id=sd_id,
        unit_id=request.unit_id,
        email=email,
        password_hash=SecurityService.get_password_hash(request.password),
        role_id=request.role_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# --- Unit Routes ---
@unit_router.post("", response_model=schemas.UnitResponse, status_code=201)
def create_unit(request: schemas.UnitCreate, db: Session = Depends(get_db)):
    unit = models.Unit(
        unit_id=request.unit_id,
        unit_name=request.unit_name.strip(),
        location=request.location,
    )
    if not unit.unit_name:
        raise HTTPException(status_code=400, detail="Unit name cannot be empty")

    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit

@unit_router.get("", response_model=list[schemas.UnitResponse])
def get_all_units(db: Session = Depends(get_db)):
    return db.query(models.Unit).order_by(models.Unit.unit_id).all()

@unit_router.get("/{unit_id}", response_model=schemas.UnitResponse)
def get_unit_details(unit_id: int, db: Session = Depends(get_db)):
    unit = db.get(models.Unit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail=f"Unit {unit_id} not found")
    return unit

# --- Auth Routes ---
@auth_router.post("/login", response_model=schemas.TokenResponse)
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()
    if not user or not SecurityService.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = SecurityService.create_token(
        {"sub": str(user.user_id)}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access"
    )
    refresh_token = SecurityService.create_token(
        {"sub": str(user.user_id)}, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh"
    )

    first_name = db.get(models.Sewadal, user.sd_id).name.split()[0] if db.get(models.Sewadal, user.sd_id) else "Unknown"    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer", "role_id": user.role_id, "unit_id": user.unit_id, "name": first_name}

@auth_router.post("/refresh", response_model=schemas.TokenResponse)
def refresh_access_token(request: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    user = get_user_from_refresh_token(request.refresh_token, db)
    revoke_token(request.refresh_token, db)
    access_token = SecurityService.create_token(
        {"sub": str(user.user_id)}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access"
    )
    refresh_token = SecurityService.create_token(
        {"sub": str(user.user_id)}, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh"
    )
    sewadal = db.get(models.Sewadal, user.sd_id)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role_id": user.role_id,
        "unit_id": user.unit_id,
        "name": sewadal.name.split()[0] if sewadal else "Unknown",
    }

@auth_router.post("/logout")
def logout(request: schemas.LogoutRequest, db: Session = Depends(get_db)):
    revoke_token(request.refresh_token, db)
    db.commit()
    return {"message": "Logout successful"}

# --- sewadal Details Routes ---
@employee_router.post("/upload")
async def upload_sewadal(
    file: UploadFile = File(...),
    unit_id: int = Query(...),
    db: Session = Depends(get_db),
):
    contents = await file.read()
    service = SewadalService(db)
    count = service.process_excel_upload(contents, unit_id)
    return {"message": f"Successfully processed {count} employee records."}

@employee_router.get("", response_model=list[schemas.SewadalResponse])
def get_sewadals_by_unit(
    unit_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    service = SewadalService(db)
    return service.get_by_unit(unit_id)

@employee_router.delete("/{sd_id}")
def delete_sewadal(
    sd_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    SewadalService(db).delete_by_id(sd_id.strip())
    return {"message": f"Sewadal {sd_id} deleted successfully"}

@database_router.post("/reset")
def reset_database_endpoint(
    request: schemas.DatabaseResetRequest,
    current_user: models.User = Depends(get_current_user),
):
    if not settings.DATABASE_RESET_ENABLED:
        raise HTTPException(status_code=404, detail="Database reset is disabled")

    reset_database()
    return {"message": "Database reset successfully. All application tables are empty."}

# --- Attendance Routes ---
@attendance_router.post("/mark")
def mark_attendance(
    request: schemas.AttendanceRequest, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user) # Protected Route
):
    service = AttendanceService(db)
    return service.mark_attendance(request.qr_token)

@attendance_router.get("/report", response_model=list[schemas.AttendanceRecordOut])
def get_attendance_report(
    limit: int = Query(50, ge=1, le=500),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    unit_id: int | None = Query(None, ge=1),
    gender: Literal["Male", "Female"] | None = Query(None),
    sd_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user) # Protected Route
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    service = AttendanceService(db)
    return service.get_report(limit, start_date, end_date, unit_id, gender, sd_id)

@attendance_router.get("/export", response_class=StreamingResponse)
def export_attendance_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    fieldnames = [
        "log_id",
        "sd_id",
        "log_date",
        "check_in",
        "check_out",
        "sewadal_name",
        "gender",
        "unit_id",
        "unit_name",
        "unit_location",
    ]

    def csv_rows():
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        yield output.getvalue()

        for row in AttendanceService(db).iter_export_rows():
            output.seek(0)
            output.truncate(0)
            writer.writerow(row)
            yield output.getvalue()

    return StreamingResponse(
        csv_rows(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=attendance_export.csv",
        },
    )

@attendance_router.get("/insights/kpi", response_model=schemas.AttendanceKPIResponse)
def get_attendance_insight_kpis(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    unit_id: int | None = Query(None, ge=1),
    gender: Literal["Male", "Female"] | None = Query(None),
    sd_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    parsed_start_date = _parse_query_date(start_date, "start_date")
    parsed_end_date = _parse_query_date(end_date, "end_date")
    if parsed_start_date and parsed_end_date and parsed_start_date > parsed_end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    service = AttendanceService(db)
    return service.get_insight_kpis(parsed_start_date, parsed_end_date, unit_id, gender, sd_id)

@attendance_router.get("/insights/present", response_model=schemas.AttendancePresentResponse)
def get_present_sewadals_insights(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    unit_id: int | None = Query(None, ge=1),
    gender: Literal["Male", "Female"] | None = Query(None),
    sd_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    parsed_start_date = _parse_query_date(start_date, "start_date")
    parsed_end_date = _parse_query_date(end_date, "end_date")
    if parsed_start_date and parsed_end_date and parsed_start_date > parsed_end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    service = AttendanceService(db)
    return service.get_present_sewadals(
        parsed_start_date, parsed_end_date, unit_id, gender, sd_id
    )