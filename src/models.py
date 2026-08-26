from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, JSON
from datetime import datetime
from src.database import Base

class Role(Base):
    __tablename__ = "roles"
    role_id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), unique=True, nullable=False)

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    sd_id = Column(String(50), ForeignKey("sewadals.sd_id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.unit_id"))
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"))

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(36), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

class Unit(Base):
    __tablename__ = "units"
    unit_id = Column(Integer, primary_key=True, index=True)
    unit_name = Column(String(100), nullable=False)
    location = Column(String(100),nullable=True)

class Sewadal(Base):
    __tablename__ = "sewadals"
    sd_id = Column(String(50), primary_key=True, index=True)
    email = Column(String(100), nullable=True)
    qr_token = Column(String(36), unique=True, index=True, nullable=False)
    unit_id = Column(Integer, ForeignKey("units.unit_id"))    
    gender = Column(String(10), nullable=True)
    old_p = Column(String(100), nullable = True)
    s = Column(String(50),nullable = True)
    name = Column(String(100), nullable = False)
    fathers_name = Column(String(100), nullable = False)
    date_of_add = Column(Date, nullable = True)
    date_of_birth = Column(Date, nullable = True)
    qualification = Column(String(100), nullable = True)
    occupation  = Column(String(100), nullable = True)  
    address = Column(String(200), nullable = True)
    contact_number = Column(String(100), nullable = True)
    blood_group = Column(String(30),nullable = True)
    date_of_badges = Column(Date, nullable = True)
    remarks = Column(String(100), nullable = True)
    DOE = Column(Date, nullable = True)
    date_of_delete = Column(Date, nullable = True)
    
class Attendance(Base):
    __tablename__ = "attendance"
    log_id = Column(Integer, primary_key=True, index=True)
    sd_id = Column(String(50), ForeignKey("sewadals.sd_id"), nullable=False)
    # unit_id = Column(Integer, ForeignKey("units.unit_id"), nullable=False)
    log_date = Column(Date, nullable=False)
    check_in = Column(DateTime, nullable=False)
    check_out = Column(DateTime, nullable=True)
    