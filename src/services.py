from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from fastapi import HTTPException
from datetime import date, datetime
from zoneinfo import ZoneInfo
import pandas as pd
import io
import logging
import uuid
import src.models as models
from src.database import engine
from config.constant import ADHIKARI_SHEET_NAME,FEMALE_SEWADAL_SHEET_NAME,MALE_SEWADAL_SHEET_NAME

logger = logging.getLogger(__name__)
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _insert_statement(model):
    if engine.dialect.name == "sqlite":
        return sqlite_insert(model)
    if engine.dialect.name == "mysql":
        return mysql_insert(model)
    raise RuntimeError(f"Unsupported database dialect: {engine.dialect.name}")


def _incoming_value(statement, column_name: str):
    if engine.dialect.name == "sqlite":
        return statement.excluded[column_name]
    return statement.inserted[column_name]


def _upsert_statement(statement, **updates):
    if engine.dialect.name == "sqlite":
        return statement.on_conflict_do_update(index_elements=["sd_id"], set_=updates)
    return statement.on_duplicate_key_update(**updates)


def _india_now() -> datetime:
    return datetime.now(INDIA_TIMEZONE).replace(tzinfo=None)


def _excel_date(value) -> date | None:
    if value in (None, "") or pd.isna(value):
        return None
    parsed_date = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if pd.isna(parsed_date):
        return None

    parsed_date = parsed_date.date()
    if parsed_date.year > datetime.utcnow().year:
        parsed_date = parsed_date.replace(year=parsed_date.year - 100)
    return parsed_date


def _valid_sewadal_records(dataframe: pd.DataFrame) -> list[dict]:
    sewadal_ids = dataframe["New P#"].astype("string").str.strip()
    valid_rows = dataframe.loc[sewadal_ids.notna() & sewadal_ids.ne("")].copy()
    valid_rows["New P#"] = sewadal_ids.loc[valid_rows.index]
    return valid_rows.to_dict(orient="records")


class SewadalService:
    def __init__(self, db: Session):
        self.db = db

    def delete_by_id(self, sd_id: str) -> None:
        sewadal = self.db.get(models.Sewadal, sd_id)
        if sewadal is None:
            raise HTTPException(status_code=404, detail=f"Sewadal {sd_id} not found")

        if sewadal.date_of_delete is None:
            sewadal.date_of_delete = _india_now().date()
        self.db.commit()

    def get_by_unit(self, unit_id: int):
        sewadals = (
            self.db.query(models.Sewadal)
            .filter(models.Sewadal.unit_id == unit_id)
            .filter(models.Sewadal.date_of_delete.is_(None))
            .order_by(models.Sewadal.sd_id)
            .all()
        )
        response = []
        for sewadal in sewadals:
            sewadal_data = {
                column.name: getattr(sewadal, column.name)
                for column in models.Sewadal.__table__.columns
            }
            first_name = (sewadal.name or "").strip().split(maxsplit=1)[0]
            father_name = (sewadal.fathers_name or "").strip().split()[0]
            last_name = (sewadal.name or "").strip().split(maxsplit=1)[-1] if len((sewadal.name or "").strip().split()) > 1 else (sewadal.fathers_name or "").strip().split()[-1]
            sewadal_data["name"] = " ".join(
                f"{first_name} {father_name} {last_name}"
                .replace("D/o", "")
                .replace("d/o", "")
                .replace("D/O", "")
                .split()
            )
            response.append(sewadal_data)
        return response

    def process_excel_upload(self, file_contents: bytes, unit_id: int) -> int:
        try:
            if self.db.get(models.Unit, unit_id) is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unit {unit_id} does not exist. Create the unit before uploading employees.",
                )

            adhikari_df = pd.read_excel(io.BytesIO(file_contents),sheet_name=ADHIKARI_SHEET_NAME,skiprows=2)
            
            gents_sewadal_df = pd.read_excel(io.BytesIO(file_contents),sheet_name=MALE_SEWADAL_SHEET_NAME,skiprows=2)
        
            ladies_sewadal_df = pd.read_excel(io.BytesIO(file_contents),sheet_name=FEMALE_SEWADAL_SHEET_NAME,skiprows=2)
        
            
            adhikari_df = adhikari_df.fillna("")
            gents_sewadal_df = gents_sewadal_df.fillna("")
            ladies_sewadal_df = ladies_sewadal_df.fillna("")

            adhikari_df["New P#"] = adhikari_df["Name"].apply(lambda x: str(adhikari_df["Name"][0]).split("New")[1].split("\n")[0].split(' ')[2])
            adhikari_df = adhikari_df[["New P#","Designation"]]
            # df = pd.read_excel(io.BytesIO(file_contents)).where(pd.notnull, None)
            adhikari_records = adhikari_df.to_dict(orient="records")
            gents_sewadal_records = _valid_sewadal_records(gents_sewadal_df)
            ladies_sewadal_records = _valid_sewadal_records(ladies_sewadal_df)

            processed_count = 0
            for row in gents_sewadal_records:
                stmt = _insert_statement(models.Sewadal).values(
                    sd_id=str(row['New P#']).strip(),
                    unit_id=unit_id,
                    qr_token=str(uuid.uuid4()),
                    email = None,
                    gender="Male",
                    old_p = row['Old P#'],
                    s=str(row['S#']).strip() or None,
                    name = row['Name'],
                    fathers_name = row["Father's Name"],
                    date_of_add=_excel_date(row["DO Add"]),
                    date_of_birth=_excel_date(row["DOB"]),
                    qualification = row["Quali."],
                    occupation = row["Occu."],
                    address = row["Address"],
                    contact_number = row["Contact no."],
                    blood_group = row["Blood Group"],
                    date_of_badges=_excel_date(row["DO Belt/Badges"]),
                    remarks = row["Remarks"],
                    DOE=_excel_date(row["DOE"]),
                    date_of_delete=_excel_date(row["DO Del"])

                )
                update_stmt = _upsert_statement(
                    stmt,
                    unit_id=_incoming_value(stmt, "unit_id"),
                    email=_incoming_value(stmt, "email"),
                    gender=_incoming_value(stmt, "gender"),
                    old_p=_incoming_value(stmt, "old_p"),
                    s=_incoming_value(stmt, "s"),
                    name=_incoming_value(stmt, "name"),
                    fathers_name=_incoming_value(stmt, "fathers_name"),
                    date_of_add=_incoming_value(stmt, "date_of_add"),
                    date_of_birth=_incoming_value(stmt, "date_of_birth"),
                    qualification=_incoming_value(stmt, "qualification"),
                    occupation=_incoming_value(stmt, "occupation"),
                    address=_incoming_value(stmt, "address"),
                    contact_number=_incoming_value(stmt, "contact_number"),
                    blood_group=_incoming_value(stmt, "blood_group"),
                    date_of_badges=_incoming_value(stmt, "date_of_badges"),
                    remarks=_incoming_value(stmt, "remarks"),
                    DOE=_incoming_value(stmt, "DOE"),
                    date_of_delete=_incoming_value(stmt, "date_of_delete")
                )
                self.db.execute(update_stmt)
                processed_count += 1

            for row in ladies_sewadal_records:
                stmt = _insert_statement(models.Sewadal).values(
                    sd_id=str(row['New P#']).strip(),
                    unit_id=unit_id,
                    qr_token=str(uuid.uuid4()),
                    email = None,
                    gender="Female",
                    old_p = row['Old P#'],
                    s=str(row['S#']).strip() or None,
                    name = row['Name'],
                    fathers_name = row["Father's Name"],
                    date_of_add=_excel_date(row["DO Add"]),
                    date_of_birth=_excel_date(row["DOB"]),
                    qualification = row["Quali."],
                    occupation = row["Occu."],
                    address = row["Address"],
                    contact_number = row["Contact no."],
                    blood_group = row["Blood Group"],
                    date_of_badges=_excel_date(row["DO Belt/Badges"]),
                    remarks = row["Remarks"],
                    DOE=_excel_date(row["DOE"]),
                    date_of_delete=_excel_date(row["DO Del"])

                )
                update_stmt = _upsert_statement(
                    stmt,
                    unit_id=_incoming_value(stmt, "unit_id"),
                    email=_incoming_value(stmt, "email"),
                    gender=_incoming_value(stmt, "gender"),
                    old_p=_incoming_value(stmt, "old_p"),
                    s=_incoming_value(stmt, "s"),
                    name=_incoming_value(stmt, "name"),
                    fathers_name=_incoming_value(stmt, "fathers_name"),
                    date_of_add=_incoming_value(stmt, "date_of_add"),
                    date_of_birth=_incoming_value(stmt, "date_of_birth"),
                    qualification=_incoming_value(stmt, "qualification"),
                    occupation=_incoming_value(stmt, "occupation"),
                    address=_incoming_value(stmt, "address"),
                    contact_number=_incoming_value(stmt, "contact_number"),
                    blood_group=_incoming_value(stmt, "blood_group"),
                    date_of_badges=_incoming_value(stmt, "date_of_badges"),
                    remarks=_incoming_value(stmt, "remarks"),
                    DOE=_incoming_value(stmt, "DOE"),
                    date_of_delete=_incoming_value(stmt, "date_of_delete")
                )
                self.db.execute(update_stmt)
                processed_count += 1
                        
            
            self.db.commit()
            return processed_count
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.exception("Error processing Excel upload")
            raise HTTPException(status_code=400, detail=f"Error processing Excel: {str(e)}")


class AttendanceService:
    def __init__(self, db: Session):
        self.db = db

    def iter_export_rows(self):
        query = (
            self.db.query(models.Attendance, models.Sewadal, models.Unit)
            .outerjoin(models.Sewadal, models.Attendance.sd_id == models.Sewadal.sd_id)
            .outerjoin(models.Unit, models.Sewadal.unit_id == models.Unit.unit_id)
            .order_by(models.Attendance.log_id)
            .yield_per(1000)
        )

        for attendance, sewadal, unit in query:
            yield {
                "log_id": attendance.log_id,
                "sd_id": attendance.sd_id,
                "log_date": attendance.log_date.isoformat() if attendance.log_date else "",
                "check_in": attendance.check_in.isoformat() if attendance.check_in else "",
                "check_out": attendance.check_out.isoformat() if attendance.check_out else "",
                "sewadal_name": sewadal.name if sewadal else "",
                "gender": sewadal.gender if sewadal else "",
                "unit_id": sewadal.unit_id if sewadal else "",
                "unit_name": unit.unit_name if unit else "",
                "unit_location": unit.location if unit else "",
            }

    def mark_attendance(self, qr_token: str):
        sewadal = self.db.query(models.Sewadal).filter(models.Sewadal.qr_token == qr_token).first()
        if not sewadal:
            raise HTTPException(status_code=404, detail="Invalid QR Code: Sewadal not found")

        india_now = _india_now()
        today = india_now.date()
        existing_log = self.db.query(models.Attendance).filter(
            models.Attendance.sd_id == sewadal.sd_id,
            models.Attendance.log_date == today
        ).first()

        sewadal_name = sewadal.name or "Sewadal"

        if existing_log:
            return {"status": "already_marked", "message": f"Attendance already marked for {sewadal_name} today."}

        new_attendance = models.Attendance(
            sd_id=sewadal.sd_id,
            # unit_id=unit_id,
            log_date=today, 
            check_in=india_now
        )
        self.db.add(new_attendance)
        self.db.commit()

        return {"status": "success", "message": f"Attendance marked for {sewadal_name} for today."}

    def _attendance_query(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        unit_id: int | None = None,
        gender: str | None = None,
        sd_id: str | None = None,
    ):
        query = (
            self.db.query(models.Attendance, models.Sewadal, models.Unit)
            .join(models.Sewadal, models.Attendance.sd_id == models.Sewadal.sd_id)
            .join(models.Unit, models.Sewadal.unit_id == models.Unit.unit_id)
            .filter(models.Sewadal.date_of_delete.is_(None))
        )

        if start_date:
            query = query.filter(models.Attendance.log_date >= start_date)
        if end_date:
            query = query.filter(models.Attendance.log_date <= end_date)
        if unit_id is not None:
            query = query.filter(models.Sewadal.unit_id == unit_id)
        if gender:
            query = query.filter(models.Sewadal.gender == gender)
        if sd_id:
            query = query.filter(models.Attendance.sd_id == sd_id)
        return query

    def get_report(
        self,
        limit: int = 50,
        start_date: date | None = None,
        end_date: date | None = None,
        unit_id: int | None = None,
        gender: str | None = None,
        sd_id: str | None = None,
    ):
        results = self._attendance_query(
            start_date, end_date, unit_id, gender, sd_id
        ).order_by(models.Attendance.check_in.desc()).limit(limit).all()

        report = []
        for att, sewadal, unit in results:
            first_name = (sewadal.name or "").strip().split(maxsplit=1)[0]
            father_name = (sewadal.fathers_name or "").strip().split()[0]
            last_name = (sewadal.name or "").strip().split(maxsplit=1)[-1] if len((sewadal.name or "").strip().split()) > 1 else (sewadal.fathers_name or "").strip().split()[-1]
            full_name = " ".join(
                f"{first_name} {father_name} {last_name}"
                .replace("D/o", "")
                .replace("d/o", "")
                .replace("D/O", "")
                .split()
            )
            report.append({
                "log_id": att.log_id,
                "sd_id": sewadal.sd_id,
                "sewadal_name": full_name,
                "gender": sewadal.gender,
                "unit_id": unit.unit_id,
                "date": att.log_date.isoformat(),
                "check_in": att.check_in.strftime("%I:%M %p"),
                "check_out": att.check_out.strftime("%I:%M %p") if att.check_out else None,
                "unit_name": unit.unit_name,
            })
        return report   

    def _filtered_sewadals(
        self,
        unit_id: int | None = None,
        gender: str | None = None,
        sd_id: str | None = None,
    ):
        query = self.db.query(models.Sewadal)
        query = query.filter(models.Sewadal.date_of_delete.is_(None))
        if unit_id is not None:
            query = query.filter(models.Sewadal.unit_id == unit_id)
        if gender:
            query = query.filter(models.Sewadal.gender == gender)
        if sd_id:
            query = query.filter(models.Sewadal.sd_id == sd_id)
        return query.all()

    def get_insight_kpis(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        unit_id: int | None = None,
        gender: str | None = None,
        sd_id: str | None = None,
    ):
        sewadals = self._filtered_sewadals(unit_id, gender, sd_id)
        results = self._attendance_query(
            start_date, end_date, unit_id, gender, sd_id
        ).all()
        present_ids = {sewadal.sd_id for _, sewadal, _ in results}
        total_sewadals = len(sewadals)
        male_sewadals = sum(sewadal.gender == "Male" for sewadal in sewadals)
        female_sewadals = sum(sewadal.gender == "Female" for sewadal in sewadals)
        male_present = sum(
            sewadal.gender == "Male" and sewadal.sd_id in present_ids
            for sewadal in sewadals
        )
        female_present = sum(
            sewadal.gender == "Female" and sewadal.sd_id in present_ids
            for sewadal in sewadals
        )
        return {
            "total_sewadals": total_sewadals,
            "male_sewadals": male_sewadals,
            "female_sewadals": female_sewadals,
            "total_present": len(present_ids),
            "total_absent": total_sewadals - len(present_ids),
            "male_present": male_present,
            "male_absent": male_sewadals - male_present,
            "female_present": female_present,
            "female_absent": female_sewadals - female_present,
        }

    def get_present_sewadals(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        unit_id: int | None = None,
        gender: str | None = None,
        sd_id: str | None = None,
    ):
        results = self._attendance_query(
            start_date, end_date, unit_id, gender, sd_id
        ).order_by(models.Attendance.log_date).all()
        present_by_id = {}
        daily_counts = {}

        for attendance, sewadal, unit in results:
            daily_counts[attendance.log_date] = daily_counts.get(attendance.log_date, 0) + 1
            present = present_by_id.setdefault(
                sewadal.sd_id,
                {
                    "sd_id": sewadal.sd_id,
                    "employee_name": sewadal.name or "Unknown",
                    "gender": sewadal.gender,
                    "unit_id": unit.unit_id,
                    "unit_name": unit.unit_name,
                    "attendance_count": 0,
                    "attendance_dates": [],
                },
            )
            present["attendance_count"] += 1
            present["attendance_dates"].append(attendance.log_date)

        return {
            "present_sewadals": list(present_by_id.values()),
            "daily_trend": [
                {"date": day, "count": count}
                for day, count in sorted(daily_counts.items())
            ],
        }