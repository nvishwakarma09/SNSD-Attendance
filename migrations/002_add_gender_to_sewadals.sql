USE attendance_db;

ALTER TABLE sewadals
ADD COLUMN gender VARCHAR(10) NULL AFTER unit_id;
