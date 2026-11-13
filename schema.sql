-- MySQL 8+ | banco para a API do claviculário
CREATE DATABASE IF NOT EXISTS claviculario CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE claviculario;

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  rfid_uid VARCHAR(64) NULL UNIQUE COMMENT 'UID normalizado do cartão RFID; não é senha criptográfica',
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('admin','user') NOT NULL DEFAULT 'user',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE `keys` (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  description VARCHAR(500),
  sensor_id VARCHAR(80) UNIQUE,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE reservations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  key_id INT NOT NULL,
  user_id INT NOT NULL,
  title VARCHAR(160) NOT NULL,
  starts_at DATETIME NOT NULL COMMENT 'UTC',
  ends_at DATETIME NOT NULL COMMENT 'UTC',
  status ENUM('confirmed','cancelled','completed') NOT NULL DEFAULT 'confirmed',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_reservations_key_interval (key_id, starts_at, ends_at, status),
  INDEX idx_reservations_user (user_id),
  CONSTRAINT fk_reservations_key FOREIGN KEY (key_id) REFERENCES `keys`(id),
  CONSTRAINT fk_reservations_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT chk_reservation_interval CHECK (ends_at > starts_at)
) ENGINE=InnoDB;

CREATE TABLE access_events (
  id INT AUTO_INCREMENT PRIMARY KEY,
  device_event_id VARCHAR(100) NOT NULL UNIQUE COMMENT 'ID único para reenvio seguro pelo ESP32',
  user_id INT NOT NULL,
  action ENUM('withdraw','return') NOT NULL,
  occurred_at DATETIME NOT NULL COMMENT 'UTC, horário informado pelo ESP32',
  received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_events_user_time (user_id, occurred_at),
  CONSTRAINT fk_events_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE key_loans (
  id INT AUTO_INCREMENT PRIMARY KEY,
  key_id INT NOT NULL,
  user_id INT NOT NULL,
  checkout_event_id INT NOT NULL,
  return_event_id INT NULL,
  checked_out_at DATETIME NOT NULL COMMENT 'UTC',
  returned_at DATETIME NULL COMMENT 'UTC',
  INDEX idx_loans_active (key_id, returned_at),
  INDEX idx_loans_user (user_id, checked_out_at),
  CONSTRAINT fk_loans_key FOREIGN KEY (key_id) REFERENCES `keys`(id),
  CONSTRAINT fk_loans_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_loans_checkout_event FOREIGN KEY (checkout_event_id) REFERENCES access_events(id),
  CONSTRAINT fk_loans_return_event FOREIGN KEY (return_event_id) REFERENCES access_events(id)
) ENGINE=InnoDB;
