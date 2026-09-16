-- ==========================================
-- SCRIPT DE SEGURANÇA: ATIVAÇÃO DE RLS
-- ==========================================
-- Este script habilita a Segurança em Nível de Linha (RLS) nas tabelas do seu projeto
-- e cria políticas conservadoras de leitura/escrita baseadas no auth.uid() do Supabase.

-- 1. TABELAS PÚBLICAS (LEITURA PARA TODOS, ESCRITA PARA O DONO)
DO $$ 
DECLARE
  pub_table text;
  pub_tables text[] := ARRAY['ads', 'reviews', 'groups', 'urgent_ads', 'charity_ads', 'monthly_ranking', 'regulation_posts', 'regulation_replies', 'regulation_likes', 'associations', 'artists', 'moving_sales'];
BEGIN
  FOREACH pub_table IN ARRAY pub_tables
  LOOP
    -- Checa se a tabela existe antes de rodar os comandos
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = pub_table) THEN
        -- Ativar RLS
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', pub_table);
        
        -- Remover políticas antigas
        EXECUTE format('DROP POLICY IF EXISTS "Leitura pública para todos" ON %I;', pub_table);
        EXECUTE format('DROP POLICY IF EXISTS "Inserção apenas pelo dono" ON %I;', pub_table);
        EXECUTE format('DROP POLICY IF EXISTS "Atualização apenas pelo dono" ON %I;', pub_table);
        EXECUTE format('DROP POLICY IF EXISTS "Deleção apenas pelo dono" ON %I;', pub_table);

        -- Criar política de Leitura (SELECT)
        EXECUTE format('CREATE POLICY "Leitura pública para todos" ON %I FOR SELECT USING (true);', pub_table);
        
        -- Criar políticas de Escrita (INSERT, UPDATE, DELETE)
        BEGIN
          EXECUTE format('CREATE POLICY "Inserção apenas pelo dono" ON %I FOR INSERT WITH CHECK (auth.uid() = user_id);', pub_table);
          EXECUTE format('CREATE POLICY "Atualização apenas pelo dono" ON %I FOR UPDATE USING (auth.uid() = user_id);', pub_table);
          EXECUTE format('CREATE POLICY "Deleção apenas pelo dono" ON %I FOR DELETE USING (auth.uid() = user_id);', pub_table);
        EXCEPTION WHEN undefined_column THEN
          RAISE NOTICE 'A tabela % não possui a coluna user_id ou teve erro na política de escrita.', pub_table;
        END;
    ELSE
        RAISE NOTICE 'Tabela ignorada (não existe): %', pub_table;
    END IF;
  END LOOP;
END $$;


-- 2. TABELAS PRIVADAS (LEITURA E ESCRITA APENAS PARA DONO OU ADMIN)
DO $$ 
DECLARE
  priv_table text;
  priv_tables text[] := ARRAY['users', 'payments', 'edit_history', 'notifications', 'reports'];
BEGIN
  FOREACH priv_table IN ARRAY priv_tables
  LOOP
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = priv_table) THEN
        -- Ativar RLS
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', priv_table);
        
        -- Remover políticas antigas
        EXECUTE format('DROP POLICY IF EXISTS "Acesso apenas ao dono ou admin" ON %I;', priv_table);

        BEGIN
          -- Para a tabela users, a coluna pode ser id e não user_id
          IF priv_table = 'users' THEN
            EXECUTE format('CREATE POLICY "Acesso apenas ao dono ou admin" ON %I FOR ALL USING (auth.uid() = id);', priv_table);
          ELSE
            EXECUTE format('CREATE POLICY "Acesso apenas ao dono ou admin" ON %I FOR ALL USING (auth.uid() = user_id);', priv_table);
          END IF;
        EXCEPTION WHEN undefined_column THEN
          RAISE NOTICE 'A tabela % não possui a coluna apropriada para a política.', priv_table;
        END;
    ELSE
        RAISE NOTICE 'Tabela ignorada (não existe): %', priv_table;
    END IF;
  END LOOP;
END $$;


-- 3. TABELA ADMINS
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'admins') THEN
        ALTER TABLE admins ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS "Admin tem acesso total" ON admins;
        CREATE POLICY "Admin tem acesso total" ON admins FOR ALL USING (auth.uid() = user_id);
    END IF;
END $$;


-- 4. TABELA GIFT CODES
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'gift_codes') THEN
        ALTER TABLE gift_codes ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS "Leitura publica de gift codes" ON gift_codes;
        DROP POLICY IF EXISTS "Uso de gift code por qualquer um logado" ON gift_codes;
        DROP POLICY IF EXISTS "Admin acesso total gift codes" ON gift_codes;

        CREATE POLICY "Leitura publica de gift codes" ON gift_codes FOR SELECT USING (true);
        CREATE POLICY "Uso de gift code por qualquer um logado" ON gift_codes FOR UPDATE USING (auth.uid() IS NOT NULL);
        CREATE POLICY "Admin acesso total gift codes" ON gift_codes FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);
    END IF;
END $$;
