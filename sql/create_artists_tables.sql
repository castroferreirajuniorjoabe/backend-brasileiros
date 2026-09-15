-- ==============================================================================
-- TABELAS: 'artists' e 'artist_events' (Espaço do Artista / Artistas Brasileiros)
-- Execute este script no SQL Editor do Supabase para criar as tabelas dedicadas.
-- ==============================================================================

-- 1. Tabela de Perfis de Artistas
CREATE TABLE IF NOT EXISTS public.artists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    artistic_name TEXT NOT NULL,
    area TEXT NOT NULL DEFAULT 'Música', -- Música, Dança, Teatro, Artes Visuais, Literatura, Cinema, Circo, Artesanato, Arte Digital, Outros
    bio TEXT NOT NULL,
    city TEXT NOT NULL DEFAULT 'França',
    profile_image TEXT, -- Foto de perfil principal
    gallery_images JSONB DEFAULT '[]'::jsonb, -- Até 5 imagens na galeria
    instagram TEXT,
    facebook TEXT,
    youtube TEXT,
    tiktok TEXT,
    website TEXT,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    whatsapp TEXT,
    is_featured BOOLEAN DEFAULT false,
    is_verified BOOLEAN DEFAULT false,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Tabela de Agenda / Eventos de Apresentação do Artista
CREATE TABLE IF NOT EXISTS public.artist_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_id UUID NOT NULL REFERENCES public.artists(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    event_date DATE,
    event_time TIME,
    location TEXT NOT NULL,
    city TEXT NOT NULL DEFAULT 'França',
    ticket_price NUMERIC(10, 2) DEFAULT 0.00,
    ticket_link TEXT,
    image_url TEXT,
    status TEXT NOT NULL DEFAULT 'approved', -- approved, cancelled
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Índices para consultas rápidas
CREATE INDEX IF NOT EXISTS idx_artists_status ON public.artists(status);
CREATE INDEX IF NOT EXISTS idx_artists_area ON public.artists(area);
CREATE INDEX IF NOT EXISTS idx_artists_city ON public.artists(city);
CREATE INDEX IF NOT EXISTS idx_artists_user_id ON public.artists(user_id);
CREATE INDEX IF NOT EXISTS idx_artists_created_at ON public.artists(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_artist_events_artist_id ON public.artist_events(artist_id);
CREATE INDEX IF NOT EXISTS idx_artist_events_date ON public.artist_events(event_date);

-- 4. Habilitar RLS (Row Level Security)
ALTER TABLE public.artists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artist_events ENABLE ROW LEVEL SECURITY;

-- 5. Políticas de Acesso
-- Leitura pública de artistas aprovados
CREATE POLICY "Public read approved artists" ON public.artists
    FOR SELECT USING (status = 'approved');

-- Usuários autenticados podem ver seus próprios perfis em qualquer status
CREATE POLICY "Users read own artists" ON public.artists
    FOR SELECT TO authenticated USING (auth.uid() = user_id);

-- Usuários autenticados podem criar perfil
CREATE POLICY "Users insert own artist" ON public.artists
    FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- Usuários autenticados podem atualizar seu próprio perfil
CREATE POLICY "Users update own artist" ON public.artists
    FOR UPDATE TO authenticated USING (auth.uid() = user_id);

-- Usuários autenticados podem deletar seu próprio perfil
CREATE POLICY "Users delete own artist" ON public.artists
    FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- Eventos: Leitura pública
CREATE POLICY "Public read artist events" ON public.artist_events
    FOR SELECT USING (true);

-- Eventos: Artista dono pode criar, editar e excluir
CREATE POLICY "Artist manage own events" ON public.artist_events
    FOR ALL TO authenticated USING (
        EXISTS (
            SELECT 1 FROM public.artists a 
            WHERE a.id = artist_events.artist_id AND a.user_id = auth.uid()
        )
    );
