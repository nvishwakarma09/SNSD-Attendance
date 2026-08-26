USE attendance_db;

CREATE TABLE revoked_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    jti VARCHAR(36) NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    INDEX ix_revoked_tokens_jti (jti)
);
