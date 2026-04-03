-- ===================================
-- IA Jurídica - Inicialização do Banco PostgreSQL
-- ===================================

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Para busca textual

-- Criar schema
CREATE SCHEMA IF NOT EXISTS ia_juridica;

-- Configurações de busca em português
-- DROP TEXT SEARCH CONFIGURATION IF EXISTS portuguese_unaccent;
-- CREATE TEXT SEARCH CONFIGURATION portuguese_unaccent (COPY = portuguese);

-- Índices para busca full-text serão criados pelo SQLAlchemy

-- Grants (ajustar conforme necessário)
-- GRANT ALL PRIVILEGES ON SCHEMA ia_juridica TO ia_juridica;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ia_juridica TO ia_juridica;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA ia_juridica TO ia_juridica;

-- Log de inicialização
DO $$
BEGIN
    RAISE NOTICE 'Database ia_juridica inicializado com sucesso!';
END $$;
