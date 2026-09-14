-- ==============================================================================
-- Tabela: moving_sales (Mudança & Vendas / Estou de Mudança)
-- Projeto: Brasileiros na França
-- Descrição: Desapegos, móveis, eletrodomésticos e itens de mudança
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.moving_sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Móveis',
    condition TEXT NOT NULL DEFAULT 'usado', -- 'novo', 'seminovo', 'usado'
    price NUMERIC(10, 2) NOT NULL DEFAULT 0.00, -- 0 para Doação / Grátis
    city TEXT NOT NULL,
    address TEXT,
    phone TEXT NOT NULL,
    images JSONB DEFAULT '[]'::jsonb, -- array de até 5 URLs de imagens
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'sold'
    rejection_reason TEXT,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Índices para performance em buscas e listagens
CREATE INDEX IF NOT EXISTS idx_moving_sales_status ON public.moving_sales(status);
CREATE INDEX IF NOT EXISTS idx_moving_sales_available ON public.moving_sales(is_available);
CREATE INDEX IF NOT EXISTS idx_moving_sales_user_id ON public.moving_sales(user_id);
CREATE INDEX IF NOT EXISTS idx_moving_sales_category ON public.moving_sales(category);
CREATE INDEX IF NOT EXISTS idx_moving_sales_city ON public.moving_sales(city);
CREATE INDEX IF NOT EXISTS idx_moving_sales_created_at ON public.moving_sales(created_at DESC);

-- Habilitar RLS
ALTER TABLE public.moving_sales ENABLE ROW LEVEL SECURITY;

-- Políticas de acesso (Row Level Security)
-- 1. Qualquer usuário pode visualizar anúncios de mudança aprovados e disponíveis
DROP POLICY IF EXISTS "Public can view approved moving sales" ON public.moving_sales;
CREATE POLICY "Public can view approved moving sales"
    ON public.moving_sales
    FOR SELECT
    USING (status = 'approved' AND is_available = TRUE);

-- 2. Usuários autenticados podem ver seus próprios anúncios (mesmo pendentes ou vendidos)
DROP POLICY IF EXISTS "Users can view own moving sales" ON public.moving_sales;
CREATE POLICY "Users can view own moving sales"
    ON public.moving_sales
    FOR SELECT
    USING (auth.uid() = user_id);

-- 3. Usuários autenticados podem criar anúncios de mudança
DROP POLICY IF EXISTS "Authenticated users can create moving sales" ON public.moving_sales;
CREATE POLICY "Authenticated users can create moving sales"
    ON public.moving_sales
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- 4. Usuários podem editar/atualizar seus próprios anúncios
DROP POLICY IF EXISTS "Users can update own moving sales" ON public.moving_sales;
CREATE POLICY "Users can update own moving sales"
    ON public.moving_sales
    FOR UPDATE
    USING (auth.uid() = user_id);

-- 5. Usuários podem excluir seus próprios anúncios
DROP POLICY IF EXISTS "Users can delete own moving sales" ON public.moving_sales;
CREATE POLICY "Users can delete own moving sales"
    ON public.moving_sales
    FOR DELETE
    USING (auth.uid() = user_id);
