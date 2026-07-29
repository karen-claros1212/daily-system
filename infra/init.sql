-- init.sql
-- Configuración inicial de PostgreSQL para Daily System

SELECT 'CREATE DATABASE cobro' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'cobro')\gexec

-- Extensión para UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
