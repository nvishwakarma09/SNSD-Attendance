USE attendance_db;

ALTER TABLE sewadals
MODIFY COLUMN date_of_add DATE NULL,
MODIFY COLUMN date_of_birth DATE NULL,
MODIFY COLUMN date_of_badges DATE NULL,
MODIFY COLUMN date_of_exit DATE NULL,
MODIFY COLUMN date_of_delete DATE NULL;
