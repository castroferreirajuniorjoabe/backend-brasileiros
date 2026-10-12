-- Correção: tornar coluna email da tabela ads opcional (nullable)
-- Executar no painel do Supabase > SQL Editor

-- Remove a constraint NOT NULL da coluna email na tabela ads
ALTER TABLE ads ALTER COLUMN email DROP NOT NULL;

-- Define string vazia como padrão para evitar erros em inserts antigos
ALTER TABLE ads ALTER COLUMN email SET DEFAULT '';

-- Atualiza registros existentes que possam ter email como null (segurança)
UPDATE ads SET email = '' WHERE email IS NULL;
