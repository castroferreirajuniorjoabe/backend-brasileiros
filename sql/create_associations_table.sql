-- ==============================================================================
-- Tabela: associations
-- Projeto: Brasileiros na França
-- Descrição: Cadastro de associações e parceiros institucionais na França
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.associations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    city TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'cultural',
    address TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    instagram TEXT,
    facebook TEXT,
    logo_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Índices para performance em buscas e listagens
CREATE INDEX IF NOT EXISTS idx_associations_status ON public.associations(status);
CREATE INDEX IF NOT EXISTS idx_associations_user_id ON public.associations(user_id);
CREATE INDEX IF NOT EXISTS idx_associations_city ON public.associations(city);
CREATE INDEX IF NOT EXISTS idx_associations_type ON public.associations(type);
CREATE INDEX IF NOT EXISTS idx_associations_created_at ON public.associations(created_at DESC);

-- Habilitar RLS se necessário
ALTER TABLE public.associations ENABLE ROW LEVEL SECURITY;

-- Políticas de acesso
-- 1. Qualquer usuário pode visualizar associações aprovadas
DROP POLICY IF EXISTS "Public can view approved associations" ON public.associations;
CREATE POLICY "Public can view approved associations"
    ON public.associations
    FOR SELECT
    USING (status = 'approved');

-- 2. Usuários autenticados podem ver suas próprias associações
DROP POLICY IF EXISTS "Users can view own associations" ON public.associations;
CREATE POLICY "Users can view own associations"
    ON public.associations
    FOR SELECT
    USING (auth.uid() = user_id);

-- 3. Usuários autenticados podem criar associações
DROP POLICY IF EXISTS "Authenticated users can create associations" ON public.associations;
CREATE POLICY "Authenticated users can create associations"
    ON public.associations
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- 4. Usuários podem editar/excluir suas próprias associações
DROP POLICY IF EXISTS "Users can delete own associations" ON public.associations;
CREATE POLICY "Users can delete own associations"
    ON public.associations
    FOR DELETE
    USING (auth.uid() = user_id);

-- 5. Service role / Admins possuem acesso total
DROP POLICY IF EXISTS "Service role full access on associations" ON public.associations;
CREATE POLICY "Service role full access on associations"
    ON public.associations
    FOR ALL
    USING (true)
    WITH CHECK (true);
