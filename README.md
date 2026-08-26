# Sewadal Attendance Backend

## Run with Docker

Build the image:

```bash
docker build -t sewadal-attendance-backend .
```

Run with SQLite (the database is persisted in the `attendance-data` volume):

```bash
docker volume create attendance-data
docker run --rm -p 8000:8000 \
  -v attendance-data:/app/data \
  --name sewadal-attendance-backend \
  sewadal-attendance-backend
```

The API is available at `http://localhost:8000/docs`.

## Switch to MySQL

Pass a MySQL SQLAlchemy URL when starting the container:

```bash
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=mysql+pymysql://username:password@host.docker.internal:3306/attendance_db \
  -e SECRET_KEY=replace-with-a-strong-secret \
  --name sewadal-attendance-backend \
  sewadal-attendance-backend
```

For a MySQL container running in the same Docker network, use the MySQL service name instead of `host.docker.internal`.
