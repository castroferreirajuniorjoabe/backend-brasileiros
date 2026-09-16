-- Adiciona o campo user_type à tabela users
ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type TEXT DEFAULT 'user';

-- Cria a tabela consulate_posts
CREATE TABLE IF NOT EXISTS consulate_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    consulate TEXT NOT NULL CHECK (consulate IN ('paris', 'marseille')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    event_date DATE,
    event_time TIME,
    location TEXT,
    category TEXT DEFAULT 'evento',
    image_url TEXT,
    official_link TEXT,
    is_official BOOLEAN DEFAULT TRUE,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ativar RLS
ALTER TABLE consulate_posts ENABLE ROW LEVEL SECURITY;

-- Políticas de RLS
-- Permitir leitura pública (active)
CREATE POLICY "Leitura publica de postagens ativas do consulado" ON consulate_posts
    FOR SELECT USING (status = 'active');
