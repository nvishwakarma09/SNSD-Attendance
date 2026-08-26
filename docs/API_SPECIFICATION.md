# Sewadal Attendance API Specification

## 1. Overview

The Sewadal Attendance API is a FastAPI service for:

- Authenticating users with access and refresh tokens.
- Creating roles, users, and units.
- Importing Sewadal records from Excel workbooks.
- Marking attendance using a Sewadal QR token.
- Reading attendance reports.

### Base URL

```text
http://localhost:8000
```

The API is versioned through its application metadata rather than a URL prefix. The OpenAPI document is available at:

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

### Root Check

```http
GET /
```

#### Success Response: `200 OK`

```json
{
  "message": "Attendance API is running. Visit /docs for Swagger UI."
}
```

### Content Types

- JSON endpoints use `Content-Type: application/json`.
- Excel upload uses `multipart/form-data`.
- Protected endpoints use `Authorization: Bearer <access_token>`.

---

## 2. Authentication

The API uses JWT tokens signed with the configured `SECRET_KEY` and `ALGORITHM`.

### Token Types

| Token | Purpose | Default lifetime |
|---|---|---:|
| Access token | Authorizes protected API requests | 30 minutes |
| Refresh token | Obtains a new access token | 30 days |

Token lifetime settings are configured in `config/setting.py`:

```python
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30
```

### Protected Endpoints

The following endpoints require an access token:

- `POST /api/attendance/mark`
- `GET /api/attendance/report`

Role, user, unit, and Excel upload endpoints currently do not enforce authentication in the router implementation.

---

## 3. Authentication Endpoints

### 3.1 Login

```http
POST /api/auth/login
Content-Type: application/json
```

Authenticates a user by email and password.

#### Request

```json
{
  "email": "user@example.com",
  "password": "Snmsewadal218@2025!"
}
```

Passwords must not exceed 72 UTF-8 bytes because bcrypt is used for password hashing.

#### Success Response: `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role_id": 1
}
```

`role_id` may be `null` when the user has no assigned role.

#### Errors

| Status | Condition |
|---:|---|
| `401` | Email or password is incorrect |
| `422` | Request validation failed, including a password over 72 bytes |

---

### 3.2 Refresh Tokens

```http
POST /api/auth/refresh
Content-Type: application/json
```

Validates a refresh token, revokes it, and issues a new access token and refresh token. This rotation prevents the same refresh token from being reused.

#### Request

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Success Response: `200 OK`

```json
{
  "access_token": "new-access-token",
  "refresh_token": "new-refresh-token",
  "token_type": "bearer",
  "role_id": 1
}
```

#### Errors

| Status | Condition |
|---:|---|
| `401` | Token is invalid, expired, has the wrong token type, or its user no longer exists |
| `422` | `refresh_token` is missing |

---

### 3.3 Using an Access Token

```http
Authorization: Bearer <access_token>
```

Access tokens contain a JWT `type` claim with value `access`. Refresh tokens contain `type: refresh` and cannot authorize protected attendance endpoints.

### 3.4 Logout

```http
POST /api/auth/logout
Content-Type: application/json
```

Revokes the supplied refresh token. The mobile app should delete both its access and refresh tokens after a successful response. The current access token remains valid until its normal expiry.

#### Request

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Success Response: `200 OK`

```json
{
  "message": "Logout successful"
}
```

#### Errors

| Status | Condition |
|---:|---|
| `401` | Refresh token is invalid, expired, revoked, or has the wrong token type |
| `422` | `refresh_token` is missing |

---

## 4. Role Endpoints

### 4.1 Create Role

```http
POST /api/roles
Content-Type: application/json
```

Creates a role. `role_name` is trimmed before storage and must be unique.

#### Request

```json
{
  "role_name": "Administrator"
}
```

#### Success Response: `201 Created`

```json
{
  "role_id": 1,
  "role_name": "Administrator"
}
```

#### Errors

| Status | Condition |
|---:|---|
| `400` | Role name is empty or contains only whitespace |
| `409` | A role with the same name already exists |
| `422` | Request body is missing or malformed |

---

## 5. Unit Endpoints

### 5.1 Create Unit

```http
POST /api/units
Content-Type: application/json
```

Creates a unit using the client-supplied `unit_id`.

#### Request

```json
{
  "unit_id": 218,
  "unit_name": "Mumbai Unit",
  "location": "Mumbai"
}
```

`location` is optional and defaults to `null`.

#### Success Response: `201 Created`

```json
{
  "unit_id": 218,
  "unit_name": "Mumbai Unit",
  "location": "Mumbai"
}
```

#### Errors

| Status | Condition |
|---:|---|
| `400` | Unit name is empty or contains only whitespace |
| `500` | `unit_id` already exists and the database rejects the duplicate key |
| `422` | Required field or field type is invalid |

---

### 5.2 Get All Units

```http
GET /api/units
```

Returns all units ordered by `unit_id` ascending.

#### Success Response: `200 OK`

```json
[
  {
    "unit_id": 218,
    "unit_name": "Mumbai Unit",
    "location": "Mumbai"
  },
  {
    "unit_id": 219,
    "unit_name": "Pune Unit",
    "location": "Pune"
  }
]
```

An empty database returns an empty array:

```json
[]
```

---

### 5.3 Get Unit Details

```http
GET /api/units/{unit_id}
```

#### Example

```http
GET /api/units/218
```

#### Success Response: `200 OK`

```json
{
  "unit_id": 218,
  "unit_name": "Mumbai Unit",
  "location": "Mumbai"
}
```

#### Errors

| Status | Condition |
|---:|---|
| `404` | Unit does not exist |
| `422` | `unit_id` is not an integer |

---

## 6. User Endpoints

### 6.1 Create User

```http
POST /api/users
Content-Type: application/json
```

Creates an application user. The referenced Sewadal and Unit must already exist. If `role_id` is supplied, that role must also exist.

The password is hashed with bcrypt and is never returned in the response.

#### Request

```json
{
  "sd_id": "SNSD199612167",
  "unit_id": 218,
  "email": "user@example.com",
  "password": "Snmsewadal218@2025!",
  "role_id": 1
}
```

`role_id` is optional and defaults to `null`.

#### Success Response: `201 Created`

```json
{
  "user_id": 1,
  "sd_id": "SNSD199612167",
  "unit_id": 218,
  "email": "user@example.com",
  "role_id": 1
}
```

Email is trimmed and converted to lowercase before storage.

#### Errors

| Status | Condition |
|---:|---|
| `400` | `sd_id`, email, or password is empty |
| `404` | Sewadal, Unit, or supplied Role does not exist |
| `409` | Email is already registered |
| `422` | Request is malformed or password exceeds 72 UTF-8 bytes |

---

## 7. Sewadal Endpoints

### 7.1 Upload Sewadal Excel Data

```http
POST /api/sewadals/upload?unit_id=218
Content-Type: multipart/form-data
```

Uploads an Excel workbook and imports records from the configured male and female Sewadal sheets. The referenced Unit must already exist.

#### Form Data

| Field | Type | Required | Description |
|---|---|---:|---|
| `file` | File | Yes | Excel workbook containing the configured sheets |
| `unit_id` | Integer query parameter | Yes | Existing Unit ID assigned to imported records |

#### Example with cURL

```bash
curl -X POST "http://localhost:8000/api/sewadals/upload?unit_id=218" \
  -F "file=@sewadal_data.xlsx"
```

#### Success Response: `200 OK`

```json
{
  "message": "Successfully processed 125 employee records."
}
```

#### Import Rules

- Male/Gents sheet records receive `gender: "Male"`.
- Female/Ladies sheet records receive `gender: "Female"`.
- Alphanumeric IDs such as `SNSD199612167` are stored as strings.
- The `s` field is stored as a string because spreadsheet values may contain values such as `X`.
- Excel date values are converted to Python dates.
- Blank dates are converted to `null`.
- Existing records are updated using an upsert keyed by `sd_id`.
- Existing `qr_token` values are preserved during duplicate updates.

#### Errors

| Status | Condition |
|---:|---|
| `400` | Workbook parsing, validation, or database import failure |
| `404` | Supplied Unit does not exist |
| `422` | `unit_id` is missing or invalid, or the file field is missing |

### 7.2 Get Sewadals by Unit

```http
GET /api/sewadals?unit_id=218
Authorization: Bearer <access_token>
```

Returns all Sewadals assigned to the specified Unit ID, including their full details and `qr_token`, ordered by Sewadal ID.

#### Errors

| Status | Condition |
|---:|---|
| `401` | Access token is missing, invalid, expired, or is a refresh token |
| `422` | `unit_id` is missing or not a positive integer |

---

## 8. Attendance Endpoints

### 8.1 Mark Attendance

```http
POST /api/attendance/mark
Authorization: Bearer <access_token>
Content-Type: application/json
```

Marks attendance for the Sewadal identified by the QR token. A Sewadal can be marked once per day.

#### Request

```json
{
  "qr_token": "ec0ba992-a0a2-4011-8f1c-4c2598387523",
  "unit_id": 218
}
```

#### Success Response: `200 OK`

```json
{
  "status": "success",
  "message": "Attendance marked for Sakal Narayan for today."
}
```

#### Already Marked Response: `200 OK`

```json
{
  "status": "already_marked",
  "message": "Attendance already marked for Sakal Narayan today."
}
```

#### Errors

| Status | Condition |
|---:|---|
| `401` | Access token is missing, invalid, expired, or is a refresh token |
| `404` | QR token does not identify a Sewadal |
| `422` | Request body is malformed |

---

### 8.2 Get Attendance Report

```http
GET /api/attendance/report?start_date=2026-08-01&end_date=2026-08-23&unit_id=218&gender=Female&limit=50
Authorization: Bearer <access_token>
```

Returns attendance records with Sewadal and Unit details. Results are ordered by most recent check-in first. All filters are optional.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---:|---:|---|
| `start_date` | Date (`YYYY-MM-DD`) | No | None | Include records on or after this date |
| `end_date` | Date (`YYYY-MM-DD`) | No | None | Include records on or before this date |
| `unit_id` | Integer | No | None | Filter by Unit |
| `gender` | String | No | None | Filter by `Male` or `Female` |
| `sd_id` | String | No | None | Filter by one Sewadal ID |
| `limit` | Integer | No | `50` | Maximum records returned; allowed range is 1-500 |

#### Success Response: `200 OK`

```json
[
  {
    "log_id": 42,
    "sd_id": "SNSD199612167",
    "employee_name": "Sakal Narayan",
    "gender": "Male",
    "unit_id": 218,
    "date": "2026-08-23",
    "check_in": "05:41 PM",
    "check_out": null,
    "unit_name": "Mumbai Unit"
  }
]
```

#### Errors

| Status | Condition |
|---:|---|
| `401` | Access token is missing, invalid, expired, or is a refresh token |
| `422` | `limit` is not an integer |

`400` is returned when `start_date` is later than `end_date`.

---

### 8.3 Attendance KPI Insights

```http
GET /api/attendance/insights/kpi?start_date=2026-08-01&end_date=2026-08-23&unit_id=218
Authorization: Bearer <access_token>
```

Returns attendance KPI counts using the same optional filters as the report endpoint, except `limit`.

`start_date` and `end_date` accept these formats: `YYYY-MM-DD`, `YYYY/MM/DD`,
`DD-MM-YYYY`, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD.MM.YYYY`, and month-name forms
such as `24 Aug 2026` or `Aug 24, 2026`. Numeric dates with a day and month
between 1 and 12 can be ambiguous; use `YYYY-MM-DD` when possible.

#### Success Response: `200 OK`

```json
{
  "total_sewadals": 150,
  "male_sewadals": 90,
  "female_sewadals": 60,
  "total_present": 83,
  "total_absent": 67,
  "male_present": 50,
  "male_absent": 40,
  "female_present": 33,
  "female_absent": 27
}
```

#### KPI Definitions

- `total_sewadals`: Number of Sewadals matching the unit, gender, and ID filters.
- `male_sewadals` and `female_sewadals`: Gender counts among the filtered Sewadals.
- `total_present` and `total_absent`: Filtered Sewadals with and without attendance in the selected date range.
- `male_present` and `male_absent`: Male Sewadals with and without attendance in the selected date range.
- `female_present` and `female_absent`: Female Sewadals with and without attendance in the selected date range.

### 8.4 Present Sewadals and Trends

```http
GET /api/attendance/insights/present?start_date=2026-08-01&end_date=2026-08-23&unit_id=218
Authorization: Bearer <access_token>
```

Returns each unique Sewadal with attendance in the selected date range and a daily attendance trend.

#### Success Response: `200 OK`

```json
{
  "present_sewadals": [
    {
      "sd_id": "SNSD199612167",
      "employee_name": "Sakal Narayan",
      "gender": "Male",
      "unit_id": 218,
      "unit_name": "Mumbai Unit",
      "attendance_count": 3,
      "attendance_dates": ["2026-08-21", "2026-08-22", "2026-08-23"]
    }
  ],
  "daily_trend": [
    {"date": "2026-08-22", "count": 61},
    {"date": "2026-08-23", "count": 64}
  ]
}
```

`start_date` and `end_date` accept the date formats documented for the report endpoint. Both new endpoints return `400` when `start_date` is later than `end_date`.

The previous combined `/api/attendance/insights` endpoint has been replaced by the KPI and present-trend endpoints.

#### Errors

| Status | Condition |
|---:|---|
| `400` | A date is invalid, or `start_date` is later than `end_date` |
| `401` | Access token is missing, invalid, expired, or is a refresh token |
| `422` | A non-date filter has an invalid type |

---

## 9. Common Error Format

FastAPI validation errors generally use this format:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

Application errors use this format:

```json
{
  "detail": "Unit 218 not found"
}
```

Unhandled exceptions are logged with a traceback and return:

```json
{
  "detail": "Internal server error"
}
```

---

## 10. Database Requirements

The SQLAlchemy models expect the following important column types:

- `sewadals.sd_id`: `VARCHAR(50)` because IDs are alphanumeric.
- `sewadals.s`: `VARCHAR(50)` because source values may be non-numeric.
- `sewadals.gender`: `VARCHAR(10)`.
- All Sewadal date fields are nullable.
- `users.sd_id` and `attendance.sd_id`: compatible string foreign keys to `sewadals.sd_id`.

For an existing database, run the migrations in order:

1. `migrations/001_allow_null_date_of_delete.sql`
2. `migrations/002_add_gender_to_sewadals.sql`
3. `migrations/003_rename_date_of_exit_to_doe.sql`

`Base.metadata.create_all()` creates missing tables but does not alter existing column types or constraints.
The checked-in migration files use MySQL syntax. Fresh SQLite databases are created
from the SQLAlchemy models automatically; existing SQLite schemas need a
SQLite-compatible migration tool or a data-backed schema recreation.

---

## 11. Typical Setup Flow

1. Create a role with `POST /api/roles`.
2. Create a unit with `POST /api/units`.
3. Upload Sewadal Excel data with `POST /api/sewadals/upload?unit_id=<unit_id>`.
4. Create a user with `POST /api/users`, referencing an imported `sd_id` and existing `unit_id`.
5. Log in with `POST /api/auth/login`.
6. Use the access token for attendance operations.
7. Use `POST /api/auth/refresh` when the access token expires.
8. Use `POST /api/auth/logout` when the mobile user signs out, then delete both local tokens.

---

## 12. Configuration

The service reads these environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy database connection | `sqlite:///./attendance.db` |
| `SECRET_KEY` | JWT signing key | Development fallback only |

SQLite is the default and requires no database server. To use MySQL, set for example:

`mysql+pymysql://username:password@localhost:3306/attendance_db`

The application selects the SQLAlchemy dialect from `DATABASE_URL` and supports
both SQLite and MySQL employee upserts.

For production, set a strong, non-default `SECRET_KEY` and a secure `DATABASE_URL` through environment configuration.
