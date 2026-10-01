-- 1. ALTER TABLE ads (adicionando campos de moradia)
DO $$
BEGIN
    -- Categoria do anúncio ('general', 'housing')
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'ads' AND column_name = 'ad_category') THEN
        ALTER TABLE ads ADD COLUMN ad_category text DEFAULT 'general';
    END IF;

    -- Campos específicos de Moradia
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'ads' AND column_name = 'property_type') THEN
        ALTER TABLE ads ADD COLUMN property_type text;
        ALTER TABLE ads ADD COLUMN living_preference text;
        ALTER TABLE ads ADD COLUMN announcer_identity text;
        
        ALTER TABLE ads ADD COLUMN accepts_pets boolean DEFAULT false;
        ALTER TABLE ads ADD COLUMN accepts_children boolean DEFAULT false;
        ALTER TABLE ads ADD COLUMN is_420_friendly boolean DEFAULT false;
        ALTER TABLE ads ADD COLUMN is_quiet_environment boolean DEFAULT false;
        ALTER TABLE ads ADD COLUMN accepts_smokers boolean DEFAULT false;
        ALTER TABLE ads ADD COLUMN accepts_couples boolean DEFAULT false;
        ALTER TABLE ads ADD COLUMN accepts_visitors boolean DEFAULT false;
        ALTER TABLE ads ADD COLUMN accepts_home_office boolean DEFAULT false;
        
        ALTER TABLE ads ADD COLUMN charges_included boolean;
        ALTER TABLE ads ADD COLUMN deposit text;
        ALTER TABLE ads ADD COLUMN surface_m2 integer;
        ALTER TABLE ads ADD COLUMN floor integer;
        ALTER TABLE ads ADD COLUMN furnished boolean;
        ALTER TABLE ads ADD COLUMN roommates_count integer;
        ALTER TABLE ads ADD COLUMN roommates_profile text;
        ALTER TABLE ads ADD COLUMN house_rules text;
        ALTER TABLE ads ADD COLUMN documents_required text[];
        ALTER TABLE ads ADD COLUMN min_stay text;
        
        ALTER TABLE ads ADD COLUMN availability_date date;
        ALTER TABLE ads ADD COLUMN start_date date;
        ALTER TABLE ads ADD COLUMN end_date date;
        ALTER TABLE ads ADD COLUMN is_unlimited boolean DEFAULT false;
        
        ALTER TABLE ads ADD COLUMN virtual_tour_link text;
        ALTER TABLE ads ADD COLUMN is_occupied boolean DEFAULT false;
    END IF;
END $$;


-- 2. CREATE TABLE housing_messages
CREATE TABLE IF NOT EXISTS housing_messages (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  ad_id uuid REFERENCES ads(id) ON DELETE CASCADE,
  sender_id uuid REFERENCES users(id) ON DELETE SET NULL,
  sender_name text NOT NULL,
  sender_email text NOT NULL,
  sender_phone text,
  message text NOT NULL,
  is_read boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);


-- 3. POLÍTICAS DE SEGURANÇA (RLS) PARA housing_messages
ALTER TABLE housing_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Usuário pode enviar mensagem para anúncios de moradia" ON housing_messages;
DROP POLICY IF EXISTS "Dono do anúncio de moradia pode ler as mensagens" ON housing_messages;
DROP POLICY IF EXISTS "Dono do anúncio de moradia pode deletar as mensagens" ON housing_messages;
DROP POLICY IF EXISTS "Admin tem acesso total às mensagens de moradia" ON housing_messages;

CREATE POLICY "Usuário pode enviar mensagem para anúncios de moradia" ON housing_messages 
FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Dono do anúncio de moradia pode ler as mensagens" ON housing_messages 
FOR SELECT USING (
    auth.uid() = (SELECT user_id FROM ads WHERE ads.id = housing_messages.ad_id)
);

CREATE POLICY "Dono do anúncio de moradia pode deletar as mensagens" ON housing_messages 
FOR DELETE USING (
    auth.uid() = (SELECT user_id FROM ads WHERE ads.id = housing_messages.ad_id)
);

CREATE POLICY "Admin tem acesso total às mensagens de moradia" ON housing_messages 
FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.is_admin = true)
);
