-- ==============================================================================
-- TABELAS PARA A SEÇÃO "DÚVIDAS DE REGULARIZAÇÃO 🇧🇷🇫🇷"
-- ==============================================================================

-- 1. Tabela de Publicações (Dúvidas e Dicas de Regularização)
CREATE TABLE IF NOT EXISTS public.regulation_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    type TEXT NOT NULL DEFAULT 'question', -- 'question' | 'tip'
    category TEXT NOT NULL DEFAULT 'vistos', -- 'vistos', 'titulo_residencia', 'naturalizacao', etc.
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    images JSONB DEFAULT '[]'::jsonb,
    likes_count INTEGER NOT NULL DEFAULT 0,
    replies_count INTEGER NOT NULL DEFAULT 0,
    is_solved BOOLEAN NOT NULL DEFAULT false,
    best_reply_id UUID,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'pending', 'hidden', 'deleted'
    views_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Tabela de Respostas
CREATE TABLE IF NOT EXISTS public.regulation_replies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES public.regulation_posts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    likes_count INTEGER NOT NULL DEFAULT 0,
    is_best_answer BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'hidden', 'deleted'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Tabela de Curtidas (Unicidade por usuário e alvo)
CREATE TABLE IF NOT EXISTS public.regulation_likes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    target_type TEXT NOT NULL, -- 'post' | 'reply'
    target_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT uq_regulation_user_target UNIQUE (user_id, target_type, target_id)
);

-- 4. Tabela de Denúncias
CREATE TABLE IF NOT EXISTS public.regulation_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    target_type TEXT NOT NULL, -- 'post' | 'reply'
    target_id UUID NOT NULL,
    reason TEXT NOT NULL,
    details TEXT,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'resolved', 'dismissed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Índices para Performance e Buscas Rápidas
CREATE INDEX IF NOT EXISTS idx_reg_posts_type_status ON public.regulation_posts(type, status);
CREATE INDEX IF NOT EXISTS idx_reg_posts_category ON public.regulation_posts(category);
CREATE INDEX IF NOT EXISTS idx_reg_posts_user ON public.regulation_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_reg_posts_created ON public.regulation_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reg_replies_post ON public.regulation_replies(post_id);
CREATE INDEX IF NOT EXISTS idx_reg_replies_user ON public.regulation_replies(user_id);
CREATE INDEX IF NOT EXISTS idx_reg_likes_target ON public.regulation_likes(target_type, target_id);
