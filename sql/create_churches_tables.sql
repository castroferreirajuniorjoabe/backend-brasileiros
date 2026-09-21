-- Tabelas para Igrejas Brasileiras

CREATE TABLE IF NOT EXISTS churches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    denomination TEXT NOT NULL,
    description TEXT,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code TEXT,
    country TEXT DEFAULT 'France',
    phone TEXT,
    whatsapp TEXT,
    email TEXT,
    website TEXT,
    instagram TEXT,
    facebook TEXT,
    youtube TEXT,
    profile_image TEXT NOT NULL,
    banner_image TEXT,
    latitude FLOAT,
    longitude FLOAT,
    services_offered TEXT[] DEFAULT '{}',
    languages TEXT[] DEFAULT '{}',
    is_verified BOOLEAN DEFAULT FALSE,
    is_featured BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_user_church ON churches(user_id);

CREATE TABLE IF NOT EXISTS church_schedule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    church_id UUID REFERENCES churches(id) ON DELETE CASCADE,
    day_of_week TEXT NOT NULL,
    time TIME NOT NULL,
    type TEXT NOT NULL,
    language TEXT,
    celebrant TEXT,
    notes TEXT,
    order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS church_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    church_id UUID REFERENCES churches(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME,
    location TEXT NOT NULL,
    image_url TEXT,
    type TEXT NOT NULL,
    registration_link TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'completed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS church_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    church_id UUID REFERENCES churches(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    group_type TEXT NOT NULL,
    meeting_day TEXT,
    meeting_time TIME,
    leader_name TEXT,
    contact TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS church_leaders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    church_id UUID REFERENCES churches(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    bio TEXT,
    photo_url TEXT,
    languages TEXT[] DEFAULT '{}',
    office_hours TEXT,
    whatsapp TEXT,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS church_social_services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    church_id UUID REFERENCES churches(id) ON DELETE CASCADE,
    service_name TEXT NOT NULL,
    description TEXT,
    how_to_access TEXT,
    responsible_name TEXT,
    contact TEXT,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Habilitar RLS
ALTER TABLE churches ENABLE ROW LEVEL SECURITY;
ALTER TABLE church_schedule ENABLE ROW LEVEL SECURITY;
ALTER TABLE church_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE church_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE church_leaders ENABLE ROW LEVEL SECURITY;
ALTER TABLE church_social_services ENABLE ROW LEVEL SECURITY;

-- Políticas para churches
CREATE POLICY "Leitura publica de igrejas aprovadas" ON churches
    FOR SELECT USING (status = 'approved');

CREATE POLICY "Dono pode gerenciar propria igreja" ON churches
    FOR ALL USING (auth.uid() = user_id);

-- Políticas para church_schedule
CREATE POLICY "Leitura publica de horarios de igrejas" ON church_schedule
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_schedule.church_id AND churches.status = 'approved')
    );

CREATE POLICY "Dono pode gerenciar horarios" ON church_schedule
    FOR ALL USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_schedule.church_id AND churches.user_id = auth.uid())
    );

-- Políticas para church_events
CREATE POLICY "Leitura publica de eventos de igrejas" ON church_events
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_events.church_id AND churches.status = 'approved')
    );

CREATE POLICY "Dono pode gerenciar eventos de igreja" ON church_events
    FOR ALL USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_events.church_id AND churches.user_id = auth.uid())
    );

-- Políticas para church_groups
CREATE POLICY "Leitura publica de grupos de igrejas" ON church_groups
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_groups.church_id AND churches.status = 'approved')
    );

CREATE POLICY "Dono pode gerenciar grupos de igreja" ON church_groups
    FOR ALL USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_groups.church_id AND churches.user_id = auth.uid())
    );

-- Políticas para church_leaders
CREATE POLICY "Leitura publica de lideres de igrejas" ON church_leaders
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_leaders.church_id AND churches.status = 'approved')
    );

CREATE POLICY "Dono pode gerenciar lideres de igreja" ON church_leaders
    FOR ALL USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_leaders.church_id AND churches.user_id = auth.uid())
    );

-- Políticas para church_social_services
CREATE POLICY "Leitura publica de servicos sociais de igrejas" ON church_social_services
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_social_services.church_id AND churches.status = 'approved')
    );

CREATE POLICY "Dono pode gerenciar servicos sociais de igreja" ON church_social_services
    FOR ALL USING (
        EXISTS (SELECT 1 FROM churches WHERE churches.id = church_social_services.church_id AND churches.user_id = auth.uid())
    );
