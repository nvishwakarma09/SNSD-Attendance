from pydantic import BaseModel, field_validator
from datetime import date
from typing import List, Optional

def validate_bcrypt_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 bytes")
    return password

class LoginRequest(BaseModel):
    email: str
    password: str

    _validate_password = field_validator("password")(validate_bcrypt_password)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role_id: Optional[int] = None
    unit_id: Optional[int] = None
    name: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str

class RoleCreate(BaseModel):
    role_name: str

class RoleResponse(BaseModel):
    role_id: int
    role_name: str

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    sd_id: str
    unit_id: int
    email: str
    password: str
    role_id: Optional[int] = None

    _validate_password = field_validator("password")(validate_bcrypt_password)

class UserResponse(BaseModel):
    user_id: int
    sd_id: str
    unit_id: int
    email: str
    role_id: Optional[int] = None

    class Config:
        from_attributes = True

class AttendanceRequest(BaseModel):
    qr_token: str
    # unit_id: int

class UnitCreate(BaseModel):
    unit_id: int
    unit_name: str
    location: Optional[str] = None

class UnitResponse(BaseModel):
    unit_id: int
    unit_name: str
    location: Optional[str] = None

    class Config:
        from_attributes = True

class SewadalResponse(BaseModel):
    sd_id: str
    email: Optional[str] = None
    qr_token: str
    unit_id: int
    gender: Optional[str] = None
    old_p: Optional[str] = None
    s: Optional[str] = None
    name: str
    fathers_name: str
    date_of_add: Optional[date] = None
    date_of_birth: Optional[date] = None
    qualification: Optional[str] = None
    occupation: Optional[str] = None
    address: Optional[str] = None
    contact_number: Optional[str] = None
    blood_group: Optional[str] = None
    date_of_badges: Optional[date] = None
    remarks: Optional[str] = None
    DOE: Optional[date] = None
    date_of_delete: Optional[date] = None

    class Config:
        from_attributes = True

class AttendanceRecordOut(BaseModel):
    log_id: int
    sd_id: str
    sewadal_name: str
    gender: Optional[str] = None
    unit_id: int
    unit_name: str
    date: str
    check_in: str
    check_out: Optional[str] = None

class AttendanceBreakdown(BaseModel):
    name: str
    count: int

class AttendanceDailyInsight(BaseModel):
    date: date
    count: int

class AttendanceKPIResponse(BaseModel):
    total_sewadals: int
    male_sewadals: int
    female_sewadals: int
    total_present: int
    total_absent: int
    male_present: int
    male_absent: int
    female_present: int
    female_absent: int

class AttendancePresentSewadal(BaseModel):
    sd_id: str
    employee_name: str
    gender: Optional[str] = None
    unit_id: int
    unit_name: str
    attendance_count: int
    attendance_dates: list[date]

class AttendancePresentResponse(BaseModel):
    present_sewadals: list[AttendancePresentSewadal]
    daily_trend: list[AttendanceDailyInsight]