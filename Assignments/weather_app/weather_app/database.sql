-- WeatherApp database
CREATE DATABASE IF NOT EXISTS weather_app
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE weather_app;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Saved cities (each row belongs to one user)
CREATE TABLE IF NOT EXISTS saved_cities (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL,
    city       VARCHAR(100) NOT NULL,
    country    VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_city (user_id, city, country),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Search history (each row belongs to one user)
CREATE TABLE IF NOT EXISTS search_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    city        VARCHAR(100) NOT NULL,
    country     VARCHAR(10) NOT NULL,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_history_user_time (user_id, searched_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
