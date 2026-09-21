-- Tabelas para Influencers Brasileiros

CREATE TABLE IF NOT EXISTS influencers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    artistic_name TEXT NOT NULL,
    real_name TEXT,
    bio TEXT,
    area TEXT NOT NULL,
    city TEXT NOT NULL,
    profile_image TEXT NOT NULL,
    banner_image TEXT,
    instagram TEXT,
    tiktok TEXT,
    youtube TEXT,
    twitter TEXT,
    other_social TEXT,
    followers_count INTEGER DEFAULT 0,
    languages TEXT[] DEFAULT '{}',
    partnership_types TEXT[] DEFAULT '{}',
    average_price TEXT,
    whatsapp TEXT,
    email TEXT NOT NULL,
    website TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    is_featured BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Evitar que um usuário crie mais de um perfil
CREATE UNIQUE INDEX IF NOT EXISTS unique_user_influencer ON influencers(user_id);

CREATE TABLE IF NOT EXISTS influencer_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    influencer_id UUID REFERENCES influencers(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME,
    location TEXT NOT NULL,
    city TEXT,
    image_url TEXT,
    registration_link TEXT,
    type TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'completed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS influencer_portfolio (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    influencer_id UUID REFERENCES influencers(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    image_url TEXT NOT NULL,
    media_type TEXT DEFAULT 'image' CHECK (media_type IN ('image', 'video')),
    brand_name TEXT,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Habilitar RLS
ALTER TABLE influencers ENABLE ROW LEVEL SECURITY;
ALTER TABLE influencer_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE influencer_portfolio ENABLE ROW LEVEL SECURITY;

-- Políticas para influencers
CREATE POLICY "Leitura publica de influencers aprovados" ON influencers
    FOR SELECT USING (status = 'approved');

CREATE POLICY "Dono pode gerenciar proprio perfil de influencer" ON influencers
    FOR ALL USING (auth.uid() = user_id);

-- Políticas para influencer_events
CREATE POLICY "Leitura publica de eventos de influencers" ON influencer_events
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM influencers WHERE influencers.id = influencer_events.influencer_id AND influencers.status = 'approved')
    );

CREATE POLICY "Dono pode gerenciar seus eventos de influencer" ON influencer_events
    FOR ALL USING (
        EXISTS (SELECT 1 FROM influencers WHERE influencers.id = influencer_events.influencer_id AND influencers.user_id = auth.uid())
    );

-- Políticas para influencer_portfolio
CREATE POLICY "Leitura publica de portfolio de influencers" ON influencer_portfolio
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM influencers WHERE influencers.id = influencer_portfolio.influencer_id AND influencers.status = 'approved')
    );

CREATE POLICY "Dono pode gerenciar seu portfolio de influencer" ON influencer_portfolio
    FOR ALL USING (
        EXISTS (SELECT 1 FROM influencers WHERE influencers.id = influencer_portfolio.influencer_id AND influencers.user_id = auth.uid())
    );
