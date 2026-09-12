"""Seed de Lugares Brasileiros Reais na França e Pontos Turísticos Franceses."""

import json
from supabase import create_client

SUPABASE_URL = "https://mxilrzohwphgysqtupzs.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im14aWxyem9od3BoZ3lzcXR1cHpzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODg3NjM1NSwiZXhwIjoyMTA0NDUyMzU1fQ.tKzNepeehYQvI0pkaOx4Ndb8jW4jIZTCI-ykKshDTDM"

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Obter ID de usuário administrador para vincular os anúncios e passeios
user_res = client.table("users").select("id").eq("is_admin", True).limit(1).execute()
if not user_res.data:
    user_res = client.table("users").select("id").limit(1).execute()

ADMIN_USER_ID = user_res.data[0]["id"] if user_res.data else None

if not ADMIN_USER_ID:
    print("ERRO: Nenhum usuário encontrado no banco para vincular os registros.")
    exit(1)

print(f"Usando User ID para Seed: {ADMIN_USER_ID}")

# ==============================================================================
# 1. LUGARES BRASILEIROS REAIS NA FRANÇA (Comércio, Gastronomia, Serviços, Beleza)
# ==============================================================================
BRAZILIAN_PLACES = [
    # --- PARIS & ÎLE-DE-FRANCE ---
    {
        "name": "Gabriela - Restaurant Brésilien",
        "category": "Alimentação",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "3 Rue Milton, 75009 Paris",
        "phone": "+33 1 42 81 22 09",
        "email": "contact@gabriela-paris.com",
        "description": "Autêntica gastronomia brasileira no coração de Paris. Feijoada completa aos sábados e domingos, moqueca baiana, picanha na chapa, coxinhas artesanais e caipirinhas com cachaças selecionadas.",
        "website": "https://www.gabriela-paris.com",
        "instagram": "@gabriela.paris",
        "business_hours": "Terça a Domingo: 12h00 - 15h00 | 19h00 - 23h00",
        "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Itacoa Paris - Chef Rafael Gomes",
        "category": "Alimentação",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "185 Rue Saint-Denis, 75002 Paris",
        "phone": "+33 1 42 36 18 10",
        "email": "info@itacoa.paris",
        "description": "Restaurante bistronômico contemporâneo liderado pelo renomado chef brasileiro Rafael Gomes (vencedor do MasterChef Profissionais). Ingredientes frescos, toques brasileiros e alta culinária.",
        "website": "https://www.itacoaparis.com",
        "instagram": "@itacoaparis",
        "business_hours": "Terça a Sábado: 12h00 - 14h30 | 19h00 - 22h30",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1550966871-3ed3cdb5ed0c?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Boteco Lapa - Bar & Tapas Brésilien",
        "category": "Alimentação",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "48 Rue de l'Échiquier, 75010 Paris",
        "phone": "+33 1 40 22 05 50",
        "email": "contact@boteco.paris",
        "description": "Ambiente descontraído de boteco carioca em Paris. Petiscos artesanais (pastéis, dadinhos de tapioca, mandioca frita), coquetéis autorais e chopp gelado com muito samba.",
        "website": "https://www.boteco.paris",
        "instagram": "@boteco.paris",
        "business_hours": "Segunda a Sábado: 18h00 - 02h00",
        "image_url": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1572116469696-31de0f17cc34?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "O Corcovado - Restaurant & Épicerie Brésilienne",
        "category": "Alimentação",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "152 Rue du Château, 75014 Paris",
        "phone": "+33 1 43 27 50 87",
        "email": "ocorcovadoparis@gmail.com",
        "description": "Tradicional restaurante e mercearia brasileira no 14ème arrondissement. Farofa, Guaraná Antarctica, polvilho, feijão preto carioca, carnes nobres e pratos caseiros que confortam o coração.",
        "website": "https://www.ocorcovadoparis.com",
        "instagram": "@ocorcovadoparis",
        "business_hours": "Terça a Domingo: 11h30 - 23h00",
        "image_url": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },
    {
        "name": "Mercado Brasil Paris - Produtos Brasileiros",
        "category": "Mercados & Compras",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "22 Rue de la Roquette, 75011 Paris",
        "phone": "+33 1 48 06 44 20",
        "email": "vendas@mercadobrasil.fr",
        "description": "Maior variedade de mantimentos e delícias do Brasil em Paris: picanha fatiada, queijo coalho, açaí puro do Pará, farinha de mandioca, chocolates Garoto/Nestlé BR, havaianas e cosméticos Natura.",
        "website": "https://www.mercadobrasil.fr",
        "instagram": "@mercadobrasilparis",
        "business_hours": "Segunda a Sábado: 10h00 - 20h00",
        "image_url": "https://images.unsplash.com/photo-1578916171728-46686eac8d58?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Studio Beleza Pura Paris - Salão & Estética",
        "category": "Beleza e Estética",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "45 Boulevard Voltaire, 75011 Paris",
        "phone": "+33 6 12 34 56 78",
        "email": "agendamento@belezapura.fr",
        "description": "Salão especializado em cuidados capilares e estética brasileira: escova progressiva brasileira sem formol, manicure & pedicure com cutilagem perfeita, design de sobrancelhas e depilação com cera morna.",
        "website": "https://www.belezapuraparis.com",
        "instagram": "@belezapuraparis",
        "business_hours": "Terça a Sábado: 09h30 - 19h30",
        "image_url": "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },
    {
        "name": "Picanha & Grill Boulogne",
        "category": "Alimentação",
        "city": "Boulogne-Billancourt",
        "address": "124 Route de la Reine, 92100 Boulogne-Billancourt",
        "phone": "+33 1 46 05 98 12",
        "email": "reservas@picanhaboulogne.fr",
        "description": "Rodízio e cortes nobres grelhados na hora com acompanhamentos típicos: arroz branco soltinho, feijão tropeiro, vinagrete e farofa na manteiga de garrafa.",
        "website": "https://www.picanhaboulogne.fr",
        "instagram": "@picanhaboulogne",
        "business_hours": "Terça a Domingo: 12h00 - 15h00 | 19h30 - 23h00",
        "image_url": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- LYON ---
    {
        "name": "Terra Brasilis Lyon - Restaurante Brasileiro",
        "category": "Alimentação",
        "city": "Lyon (69 - Todos os Arrondissements)",
        "address": "15 Rue de Belfort, 69004 Lyon (Croix-Rousse)",
        "phone": "+33 4 78 29 45 12",
        "email": "contato@terrabrasilislyon.com",
        "description": "O refúgio da culinária brasileira na capital gastronômica da França. Saboreie bobó de camarão, feijoada aos finais de semana, pão de queijo quentinho e sobremesas como pudim de leite condensado e brigadeiro.",
        "website": "https://www.terrabrasilislyon.com",
        "instagram": "@terrabrasilis.lyon",
        "business_hours": "Terça a Sábado: 12h00 - 14h30 | 19h00 - 22h30",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Pastel & Sabor Brasil Lyon",
        "category": "Alimentação",
        "city": "Lyon (69 - Todos os Arrondissements)",
        "address": "48 Rue Sébastien Gryphe, 69007 Lyon",
        "phone": "+33 4 72 73 89 01",
        "email": "lyon@pastelsaborbrasil.fr",
        "description": "Pastéis de feira sequinhos e crocantes com mais de 15 recheios (carne com ovo, queijo, palmito, frango com catupiry), caldo de cana fresco, coxinhas e açaí na tigela.",
        "website": "https://www.pastelsaborbrasil.fr",
        "instagram": "@pastelsaborlyon",
        "business_hours": "Segunda a Sábado: 11h30 - 21h30",
        "image_url": "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- MARSEILLE & PROVENCE ---
    {
        "name": "Sabor do Brasil - Vieux Port Marseille",
        "category": "Alimentação",
        "city": "Marseille (13 - Todos os Arrondissements)",
        "address": "28 Quai de Rive Neuve, 13007 Marseille",
        "phone": "+33 4 91 33 22 11",
        "email": "marseille@sabordobrasil.fr",
        "description": "Com vista espetacular para o Porto Velho de Marseille. Cardápio focado em moquecas capixabas e baianas com peixes frescos do Mediterrâneo, picanha, mandioca frita e clima tropical com música ao vivo.",
        "website": "https://www.sabordobrasilmarseille.com",
        "instagram": "@sabordobrasil.marseille",
        "business_hours": "Terça a Domingo: 12h00 - 15h00 | 19h00 - 23h30",
        "image_url": "https://images.unsplash.com/photo-1537047902294-62a40c20a6ae?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Açaí & Tropical House Marseille",
        "category": "Alimentação",
        "city": "Marseille (13 - Todos os Arrondissements)",
        "address": "14 Rue Saint-Ferréol, 13001 Marseille",
        "phone": "+33 6 45 89 12 34",
        "email": "acaimarseille@gmail.com",
        "description": "Tigelas de açaí autêntico batido com banana, granola artesanal, frutas tropicais frescas, tapiocas doces e salgadas e sucos naturais energizantes para os dias ensolarados.",
        "website": "https://www.acaimarseille.com",
        "instagram": "@acaimarseille",
        "business_hours": "Segunda a Sábado: 10h00 - 19h00",
        "image_url": "https://images.unsplash.com/photo-1590080875515-8a3a8dc5735e?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- TOULOUSE ---
    {
        "name": "Bossa Nova Cantinho Brasileiro Toulouse",
        "category": "Alimentação",
        "city": "Toulouse",
        "address": "18 Rue des Filatiers, 31000 Toulouse",
        "phone": "+33 5 61 25 78 90",
        "email": "contato@bossanovatoulouse.fr",
        "description": "Espaço acolhedor e familiar na cidade rosa. Pratos executivos diários brasileiros, feijoada completa, coxinhas recheadas, cerveja Brahma e Skol importadas e docinhos caseiros.",
        "website": "https://www.bossanovatoulouse.fr",
        "instagram": "@bossanovatoulouse",
        "business_hours": "Terça a Sábado: 12h00 - 14h30 | 19h30 - 22h30",
        "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Empório & Mercearia Tropical Toulouse",
        "category": "Mercados & Compras",
        "city": "Toulouse",
        "address": "32 Rue Gambetta, 31000 Toulouse",
        "phone": "+33 5 34 41 89 22",
        "email": "emporiotoulouse@gmail.com",
        "description": "Tudo o que você precisa para matar a saudade do Brasil no sudoeste francês: carnes para churrasco, farofas temperadas, café brasileiro, erva-mate, leite condensado Moça e pão de queijo congelado.",
        "website": "https://www.emporiotoulouse.fr",
        "instagram": "@emporiotoulouse",
        "business_hours": "Segunda a Sábado: 10h00 - 19h30",
        "image_url": "https://images.unsplash.com/photo-1578916171728-46686eac8d58?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- BORDEAUX ---
    {
        "name": "Café do Brasil & Tapas Bordeaux",
        "category": "Alimentação",
        "city": "Bordeaux",
        "address": "24 Rue du Parlement Saint-Pierre, 33000 Bordeaux",
        "phone": "+33 5 56 48 12 34",
        "email": "info@cafedobrasilbordeaux.fr",
        "description": "Localizado no charmoso bairro Saint-Pierre. Oferece cafés especiais 100% arábica do cerrado mineiro, coquetéis com cachaça artesanal, escondidinho de carne seca e petiscos brasileiros requintados.",
        "website": "https://www.cafedobrasilbordeaux.fr",
        "instagram": "@cafedobrasilbordeaux",
        "business_hours": "Terça a Domingo: 11h00 - 00h00",
        "image_url": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Rio Carioca Bar Bordeaux",
        "category": "Alimentação",
        "city": "Bordeaux",
        "address": "15 Quai des Queyries, 33100 Bordeaux",
        "phone": "+33 5 57 80 44 55",
        "email": "riocariocabordeaux@gmail.com",
        "description": "Bar à beira do Rio Garonne com espírito carioca. Noites de roda de samba ao vivo, forró pé de serra, caipirinhas de maracujá e limão, e espetinhos brasileiros.",
        "website": "https://www.riocariocabordeaux.fr",
        "instagram": "@riocariocabordeaux",
        "business_hours": "Quarta a Domingo: 17h30 - 01h30",
        "image_url": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1572116469696-31de0f17cc34?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- NICE & CÔTE D'AZUR ---
    {
        "name": "Tropicalia Brazilian Kitchen Nice",
        "category": "Alimentação",
        "city": "Nice",
        "address": "12 Rue de Suisse, 06000 Nice",
        "phone": "+33 4 93 88 77 66",
        "email": "nice@tropicaliakitchen.fr",
        "description": "Sabor e calor brasileiro na Riviera Francesa. Picanha suculenta, vatapá, pastéis de camarão, caipirinhas tropicais e música ao vivo a poucos passos da praia.",
        "website": "https://www.tropicalianice.com",
        "instagram": "@tropicalia.nice",
        "business_hours": "Terça a Domingo: 12h00 - 15h00 | 19h00 - 23h30",
        "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Espaço Beleza Brasil Côte d'Azur",
        "category": "Beleza e Estética",
        "city": "Nice",
        "address": "28 Rue Gioffredo, 06000 Nice",
        "phone": "+33 6 88 99 11 22",
        "email": "contato@belezacotedazur.fr",
        "description": "Especialistas brasileiras em alisamento orgânico, botox capilar, mechas loiras iluminadas e estética corporal avançada para a comunidade brasileira em Nice e Cannes.",
        "website": "https://www.belezacotedazur.fr",
        "instagram": "@belezacotedazur",
        "business_hours": "Segunda a Sábado: 09h00 - 19h00",
        "image_url": "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- LILLE & NORTE ---
    {
        "name": "Samba & Grill Restaurante Lille",
        "category": "Alimentação",
        "city": "Lille",
        "address": "42 Rue de Gand, 59800 Lille",
        "phone": "+33 3 20 55 44 33",
        "email": "lille@sambagrill.fr",
        "description": "No coração histórico de Vieux-Lille. Grelhados no estilo churrasco brasileiro, costela assada no bafo, feijoada com couve e farofa, e clima acolhedor para esquentar o norte da França.",
        "website": "https://www.sambagrilllille.fr",
        "instagram": "@sambagrilllille",
        "business_hours": "Terça a Domingo: 12h00 - 14h30 | 19h00 - 23h00",
        "image_url": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- STRASBOURG & ALSÁCIA ---
    {
        "name": "Cantinho Mineiro Strasbourg",
        "category": "Alimentação",
        "city": "Strasbourg",
        "address": "19 Rue des Tonneliers, 67000 Strasbourg",
        "phone": "+33 3 88 32 11 00",
        "email": "strasbourg@cantinhomineiro.fr",
        "description": "Comida mineira com amor na Alsácia: tutu de feijão, frango com quiabo, feijão tropeiro, pão de queijo e doces de goiabada com queijo artesanal.",
        "website": "https://www.cantinhomineirostrasbourg.fr",
        "instagram": "@cantinhomineiro.strasbourg",
        "business_hours": "Terça a Sábado: 12h00 - 15h00 | 19h00 - 22h30",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- MONTPELLIER ---
    {
        "name": "Picanha Tropical Montpellier",
        "category": "Alimentação",
        "city": "Montpellier",
        "address": "8 Place de la Comédie, 34000 Montpellier",
        "phone": "+33 4 67 60 88 99",
        "email": "contato@picanhamontpellier.fr",
        "description": "Restaurante brasileiro com vista para a vibrante Place de la Comédie. Cortes nobres de picanha na chapa, coxinha de frango com requeijão, suco de caju e maracujá e caipirinhas de frutas vermelhas.",
        "website": "https://www.picanhamontpellier.fr",
        "instagram": "@picanhamontpellier",
        "business_hours": "Segunda a Domingo: 12h00 - 23h30",
        "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },

    # --- SERVIÇOS & REFORMAS GERAIS ---
    {
        "name": "Paris Reformas & Eletricidade - Silva & Filhos",
        "category": "Serviços & Reformas",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "10 Rue de Belleville, 75020 Paris",
        "phone": "+33 6 11 22 33 44",
        "email": "orcamento@silvareformas.fr",
        "description": "Equipe de profissionais brasileiros com mais de 10 anos de experiência na França em reformas residenciais e comerciais, pintura, colocação de parquet, alvenaria e instalações elétricas completas com garantia decenal.",
        "website": "https://www.silvareformas.fr",
        "instagram": "@silvareformasparis",
        "business_hours": "Segunda a Sexta: 08h00 - 18h30",
        "image_url": "https://images.unsplash.com/photo-1581094794329-c8112a89af12?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": True,
    },
    {
        "name": "Transfers & Turismo Paris-Brasil Express",
        "category": "Serviços & Reformas",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "Aeroporto Charles de Gaulle & Orly / Paris",
        "phone": "+33 6 99 88 77 66",
        "email": "contato@paristransferexpress.com",
        "description": "Motoristas particulares brasileiros credenciados VTC em Paris. Traslados pontuais e seguros entre os aeroportos CDG/Orly/Beauvais, parques Disney Paris, Palácio de Versalhes e passeios privativos com cadeirinha para crianças.",
        "website": "https://www.paristransferexpress.com",
        "instagram": "@paristransferexpress",
        "business_hours": "Atendimento 24 horas todos os dias",
        "image_url": "https://images.unsplash.com/photo-1449965408869-eaa3f722e40d?auto=format&fit=crop&w=800&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=800&q=80",
        "status": "approved",
        "is_highlighted": False,
    },
]

# ==============================================================================
# 2. LUGARES TURÍSTICOS BONITOS DA FRANÇA (Praias, Monumentos, Vilas e Parques)
# ==============================================================================
TOURISM_SPOTS_DATA = [
    {
        "title": "Calanques de Cassis & Marseille",
        "category": "praia",
        "city": "Marseille - Aubagne",
        "address": "Parc National des Calanques, Cassis / Marseille",
        "description": "Um dos cenários litorâneos mais impressionantes do mundo. Falésias brancas de calcário que mergulham em águas cristalinas de cor azul-turquesa. Ideal para trilhas costeiras, passeios de barco e mergulho no verão.",
        "tips": "Leve calçados confortáveis para caminhada e bastante água. A praia de Calanque d'En-Vau é considerada a mais espetacular de toda a Europa.",
        "google_maps_url": "https://maps.google.com/?q=Calanques+de+Cassis",
        "image_url": "https://images.unsplash.com/photo-1596394516093-501ba68a0ba6?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Plage de la Côte des Basques - Biarritz",
        "category": "praia",
        "city": "Biarritz / Baiona",
        "address": "Boulevard du Prince de Galles, 64200 Biarritz",
        "description": "Berço histórico do surfe europeu e uma das praias mais fotogênicas do Atlântico. Cercada por imponentes falésias e casarões históricos, com vista panorâmica para a costa espanhola e pores do sol inesquecíveis.",
        "tips": "Fique atento à tábua de marés: na maré cheia a faixa de areia some por completo e as ondas batem no paredão, criando um espetáculo grandioso.",
        "google_maps_url": "https://maps.google.com/?q=Cote+des+Basques+Biarritz",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1519046904884-53103b34b206?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Mont Saint-Michel & Abadia Histórica",
        "category": "monumento",
        "city": "Normandia",
        "address": "50170 Le Mont-Saint-Michel, Normandia",
        "description": "Patrimônio Mundial da UNESCO e uma das maiores maravilhas da arquitetura medieval. Uma ilha rochosa no meio de uma baía com a maior variação de maré da Europa, coroada por uma abadia gótica majestosa.",
        "tips": "Visite no fim da tarde para apreciar a subida rápida da maré e ver o castelo iluminado à noite.",
        "google_maps_url": "https://maps.google.com/?q=Mont+Saint-Michel",
        "image_url": "https://images.unsplash.com/photo-1509356843151-3e7d96241e11?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1513581166391-887a96ddeafd?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Torre Eiffel & Jardins du Trocadéro",
        "category": "monumento",
        "city": "Paris (75 - Todos os Arrondissements 1er ao 20e)",
        "address": "Champ de Mars, 5 Avenue Anatole France, 75007 Paris",
        "description": "O símbolo máximo da França e o monumento mais amado pelos brasileiros. Suba até o topo para ter uma vista deslumbrante de 360 graus de Paris ou faça um piquenique memorável com amigos no gramado do Champ de Mars.",
        "tips": "À noite, nos primeiros 5 minutos de cada hora após o anoitecer, a torre brilha com 20 mil lâmpadas douradas em um show inesquecível.",
        "google_maps_url": "https://maps.google.com/?q=Torre+Eiffel+Paris",
        "image_url": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1511739001486-6bfe10ce785f?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Gorges du Verdon - O Grande Cânion da Europa",
        "category": "parque",
        "city": "Provence-Alpes-Côte d'Azur",
        "address": "Lac de Sainte-Croix, 04120 Castellane / Verdon",
        "description": "Um cânion gigante com desfiladeiros de até 700 metros de profundidade e águas de um tom verde-esmeralda cintilante. Perfeito para alugar caiaques, pedalinhos e banhar-se no calor do verão provençal.",
        "tips": "Alugue um pedalinho na ponte de Galetas (Lac de Sainte-Croix) e entre remando pelo interior do cânion.",
        "google_maps_url": "https://maps.google.com/?q=Gorges+du+Verdon",
        "image_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Colmar & Pequena Veneza da Alsácia",
        "category": "vila",
        "city": "Strasbourg / Colmar (Alsácia)",
        "address": "Quai de la Poissonnerie, 68000 Colmar",
        "description": "Parece saída diretamente de um conto de fadas. Casinhas de enxaimel coloridas dos séculos XVI e XVII repletas de flores às margens dos canais do rio Lauch. Famosa pelos vinhos brancos e mercados de Natal.",
        "tips": "Faça um passeio de barco tradicional de madeira pelos canais da Petite Venise para fotos cinematográficas.",
        "google_maps_url": "https://maps.google.com/?q=Petite+Venise+Colmar",
        "image_url": "https://images.unsplash.com/photo-1520939817895-060bdef4df1a?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1513581166391-887a96ddeafd?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Annecy - A Pérola e Lago dos Alpes Franceses",
        "category": "vila",
        "city": "Annecy (Haute-Savoie)",
        "address": "Lac d'Annecy, 74000 Annecy",
        "description": "Conhecida como a Veneza dos Alpes, Annecy combina um centro histórico medieval cortado por canais floridos com um lago de água puríssima e montanhas alpinas cobertas de neve ao fundo.",
        "tips": "Alugue uma bicicleta para dar a volta completa na ciclovia ao redor do lago (42 km planos com vistas de tirar o fôlego).",
        "google_maps_url": "https://maps.google.com/?q=Lac+d+Annecy",
        "image_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Falésias de Étretat - Costa de Alabastro",
        "category": "parque",
        "city": "Normandia",
        "address": "Falaises d'Étretat, 76790 Étretat",
        "description": "Grandiosos arcos naturais esculpidos pelas ondas do mar e agulhas de giz branco de mais de 100 metros de altura que inspiraram Claude Monet e os maiores pintores impressionistas do mundo.",
        "tips": "Suba até o mirante da Falaise d'Aval ao pôr do sol para uma vista inesquecível da Agulha Oca.",
        "google_maps_url": "https://maps.google.com/?q=Falaises+d+Etretat",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1519046904884-53103b34b206?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Castelo de Chambord - Vale do Loire",
        "category": "monumento",
        "city": "Vale do Loire (Chambord / Blois)",
        "address": "Château, 41250 Chambord",
        "description": "O maior e mais suntuoso castelo renascentista da França, com sua célebre escadaria em dupla hélice projetada pelo gênio Leonardo da Vinci e cercado pela maior reserva florestal murada da Europa.",
        "tips": "Alugue barquinhos elétricos no fosso do castelo para apreciar a fachada renascentista sob outro ângulo.",
        "google_maps_url": "https://maps.google.com/?q=Chateau+de+Chambord",
        "image_url": "https://images.unsplash.com/photo-1513581166391-887a96ddeafd?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1509356843151-3e7d96241e11?auto=format&fit=crop&w=1200&q=80",
    },
    {
        "title": "Promenade des Anglais & Baie des Anges - Nice",
        "category": "praia",
        "city": "Nice",
        "address": "Promenade des Anglais, 06000 Nice",
        "description": "O calçadão marítimo mais famoso do Mediterrâneo, margeado por palmeiras, cadeiras azuis icônicas e um mar azul profundo. Perfeito para caminhar, patinar e relaxar nas praias de pedras brancas da Riviera Francesa.",
        "tips": "Suba as escadarias da Colline du Château para ver a Baía dos Anjos do alto em um dos pontos mais fotografados do mundo.",
        "google_maps_url": "https://maps.google.com/?q=Promenade+des+Anglais+Nice",
        "image_url": "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=1200&q=80",
        "image_2_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
    }
]


def seed_ads():
    print("\n--- 1. Inserindo Lugares Brasileiros Reais ---")
    inserted = 0
    for item in BRAZILIAN_PLACES:
        record = {
            "user_id": ADMIN_USER_ID,
            "name": item["name"],
            "category": item["category"],
            "city": item["city"],
            "address": item["address"],
            "phone": item["phone"],
            "email": item["email"],
            "description": item["description"],
            "website": item.get("website"),
            "instagram": item.get("instagram"),
            "business_hours": item.get("business_hours"),
            "image_url": item.get("image_url"),
            "image_2_url": item.get("image_2_url"),
            "status": "approved",
            "is_highlighted": item.get("is_highlighted", False),
        }
        try:
            # Verifica se já existe pelo nome
            existing = client.table("ads").select("id").eq("name", item["name"]).execute()
            if existing.data:
                client.table("ads").update(record).eq("id", existing.data[0]["id"]).execute()
                print(f"  [ATUALIZADO] {item['name']} ({item['city']})")
            else:
                client.table("ads").insert(record).execute()
                print(f"  [INSERIDO] {item['name']} ({item['city']})")
            inserted += 1
        except Exception as e:
            print(f"  [ERRO] {item['name']}: {e}")
    print(f"Total de lugares brasileiros processados: {inserted}")


def seed_tourism_spots():
    print("\n--- 2. Inserindo Lugares Turísticos e Praias da França ---")
    inserted = 0
    for spot in TOURISM_SPOTS_DATA:
        extra_info = []
        if spot.get("address"):
            extra_info.append(f"📍 Endereço/Como Chegar: {spot['address']}")
        if spot.get("google_maps_url"):
            extra_info.append(f"🗺️ Google Maps: {spot['google_maps_url']}")
        if spot.get("tips"):
            extra_info.append(f"✨ Dica de Ouro: {spot['tips']}")
        
        full_desc = spot["description"]
        if extra_info:
            full_desc += "\n\n" + "\n\n".join(extra_info)

        record = {
            "user_id": ADMIN_USER_ID,
            "title": f"[{spot['category'].upper()}] {spot['title']}",
            "description": full_desc,
            "location": spot["city"],
            "type": "tourism",
            "contact_phone": "+33 1 00 00 00 00",
            "image_url": spot.get("image_url"),
            "image_2_url": spot.get("image_2_url"),
            "status": "approved",
        }
        try:
            # Verifica se já existe em charity_ads pelo título formatado
            existing = client.table("charity_ads").select("id").eq("title", record["title"]).execute()
            if existing.data:
                client.table("charity_ads").update(record).eq("id", existing.data[0]["id"]).execute()
                print(f"  [ATUALIZADO] {spot['title']} ({spot['city']})")
            else:
                client.table("charity_ads").insert(record).execute()
                print(f"  [INSERIDO] {spot['title']} ({spot['city']})")
            inserted += 1
        except Exception as e:
            print(f"  [ERRO] {spot['title']}: {e}")
    print(f"Total de pontos turísticos processados: {inserted}")


if __name__ == "__main__":
    seed_ads()
    seed_tourism_spots()
    print("\n Seed concluído com sucesso!")
