-- =============================================================================
-- SMART MEDICINE REMINDER SYSTEM - RDS MYSQL DATABASE SCHEMA
-- =============================================================================

CREATE DATABASE IF NOT EXISTS smart_medicine_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE smart_medicine_db;

-- -----------------------------------------------------------------------------
-- Table: users
-- Stores patient/caregiver credentials and contact information
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    phone VARCHAR(30),
    password_hash VARCHAR(255) NOT NULL,
    notification_preference ENUM('email', 'sms', 'both') DEFAULT 'both',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Table: medicines
-- Stores prescribed medicine details, dosages, and active durations
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    medicine_name VARCHAR(150) NOT NULL,
    medicine_type VARCHAR(50) DEFAULT 'Tablet',
    dosage VARCHAR(80) NOT NULL,
    quantity INT DEFAULT 30,
    instructions VARCHAR(100) DEFAULT 'After Food',
    start_date DATE NOT NULL,
    end_date DATE NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_med_user (user_id),
    INDEX idx_med_active (active),
    INDEX idx_med_dates (start_date, end_date),
    CONSTRAINT fk_medicines_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Table: medicine_schedules
-- Stores individual daily dose timings for each medicine
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medicine_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id INT NOT NULL,
    scheduled_time VARCHAR(5) NOT NULL, -- Format HH:MM (e.g., '08:00', '13:30', '20:00')
    reminder_method ENUM('email', 'sms', 'both') DEFAULT 'both',
    INDEX idx_sched_med (medicine_id),
    INDEX idx_sched_time (scheduled_time),
    CONSTRAINT fk_schedules_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Table: medicine_logs
-- Tracks the adherence status of every scheduled dose (pending, taken, missed)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medicine_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id INT NOT NULL,
    user_id INT NOT NULL,
    scheduled_date DATE NOT NULL,
    scheduled_time VARCHAR(5) NOT NULL,
    taken_time DATETIME NULL,
    status ENUM('pending', 'taken', 'missed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_log_user_date (user_id, scheduled_date),
    INDEX idx_log_status (status),
    INDEX idx_log_composite (medicine_id, user_id, scheduled_date, scheduled_time),
    CONSTRAINT fk_logs_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
    CONSTRAINT fk_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Table: notifications
-- Audit history of all alerts sent to users via Amazon SNS
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    medicine_id INT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) DEFAULT 'reminder',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(30) DEFAULT 'sent',
    INDEX idx_notif_user (user_id),
    INDEX idx_notif_sent (sent_at),
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_notif_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
