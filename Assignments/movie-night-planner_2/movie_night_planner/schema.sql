-- =====================================================================
-- Movie Night Planner Database Schema
-- Database: MySQL 8.0+
-- =====================================================================

CREATE DATABASE IF NOT EXISTS movie_night_planners
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE movie_night_planners;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Movie Nights Table
CREATE TABLE IF NOT EXISTS movie_nights (
    id INT AUTO_INCREMENT PRIMARY KEY,
    creator_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    date DATE NOT NULL,
    category ENUM('Comedy', 'Action', 'Animation', 'Other') NOT NULL,
    description TEXT NOT NULL,
    status ENUM('open', 'finalized') NOT NULL DEFAULT 'open',
    final_movie_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_movie_nights_creator FOREIGN KEY (creator_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. Movie Choices Table
CREATE TABLE IF NOT EXISTS movie_choices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    movie_night_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    genre VARCHAR(60) NOT NULL,
    reason TEXT NOT NULL,
    poster_url VARCHAR(500) NOT NULL,
    trailer_url VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_movie_choices_night FOREIGN KEY (movie_night_id)
        REFERENCES movie_nights (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. Votes Table (One vote per user per movie night)
CREATE TABLE IF NOT EXISTS votes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    movie_night_id INT NOT NULL,
    movie_choice_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_votes_night FOREIGN KEY (movie_night_id)
        REFERENCES movie_nights (id) ON DELETE CASCADE,
    CONSTRAINT fk_votes_choice FOREIGN KEY (movie_choice_id)
        REFERENCES movie_choices (id) ON DELETE CASCADE,
    CONSTRAINT fk_votes_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT uq_user_movie_night UNIQUE (movie_night_id, user_id)
) ENGINE=InnoDB;

-- 5. Foreign Key for final_movie_id in movie_nights
-- (Added after movie_choices exists)
ALTER TABLE movie_nights
    ADD CONSTRAINT fk_movie_nights_final_movie
    FOREIGN KEY (final_movie_id)
    REFERENCES movie_choices (id)
    ON DELETE SET NULL;
