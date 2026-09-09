# Brasileiros na França — Backend (FastAPI + Supabase)

API RESTful completa para o aplicativo **Brasileiros na França**: anúncios comerciais,
avaliações, grupos parceiros, anúncios de urgência e caridade, destaques pagos via
Stripe, códigos de presente, denúncias, ranking mensal e painel administrativo.

## Stack

- **FastAPI** — framework da API
- **Supabase** (cliente async) — banco de dados PostgreSQL
- **Pydantic v2** — validação de dados
- **JWT (PyJWT)** — autenticação
- **Stripe** — pagamentos (destaque €2/semana)
- **Twilio** — verificação de telefone por SMS
- **Cloudinary** — upload de imagens/documentos
- **APScheduler** — cron jobs (ranking mensal, expiração de urgências)
- **aiosmtplib** — envio de emails de verificação

## Estrutura

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py            # App FastAPI, CORS, scheduler
│   ├── config.py          # Variáveis de ambiente (pydantic-settings)
│   ├── database.py        # Clientes Supabase (anon + service_role)
│   ├── models/            # Enums, tabelas e regras de negócio
│   ├── schemas/           # Schemas Pydantic v2
│   ├── routes/            # Endpoints (auth, ads, reviews, etc.)
│   ├── utils/             # JWT, email, SMS, imagens, destaque
│   └── admin/             # Rotas administrativas
├── requirements.txt
├── .env.example
└── README.md
```

## Como rodar

### 1. Clonar e criar ambiente virtual

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Preencha o `.env` com:

| Variável | Onde obter |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API |
| `SECRET_KEY` | Gere com `openssl rand -hex 32` |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Dashboard Stripe → Developers |
| `SMTP_*` | Senha de app do Gmail ou outro provedor SMTP |
| `TWILIO_*` | Console Twilio |
| `CLOUDINARY_*` | Dashboard Cloudinary |

### 3. Subir o servidor

```bash
uvicorn app.main:app --reload --port 8000
```

- Documentação interativa (Swagger): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

### 4. Webhook do Stripe (desenvolvimento)

```bash
stripe listen --forward-to localhost:8000/payments/webhook
# Copie o "whsec_..." exibido para STRIPE_WEBHOOK_SECRET no .env
```

Em produção, cadastre o endpoint `https://seu-dominio/payments/webhook` no dashboard
do Stripe com os eventos `checkout.session.completed`, `checkout.session.expired` e
`payment_intent.payment_failed`.

## Regras de negócio implementadas

| Regra | Onde |
|---|---|
| Visitantes navegam sem login | Endpoints `GET` públicos (ads, groups, urgent, charity, ranking) |
| Anunciar exige email + telefone verificados | `get_current_verified_user` em `POST /ads` |
| 1º anúncio passa por moderação manual; seguintes são automáticos | `POST /ads` |
| Edição: máx. 2/mês, sempre com moderação | `PUT /ads/{id}` + tabela `edit_history` |
| Soft delete de anúncios | `DELETE /ads/{id}` (status = `deleted`) |
| Destaque €2/semana via Stripe | `POST /payments/checkout` + webhook |
| Top 3 do mês ganham 1 semana de destaque grátis | cron `monthly_ranking` (dia 1, 03h) |
| Urgência: BO obrigatório para desaparecidos, expira em 7 dias | `POST /urgent-ads` + cron diário |
| Caridade: 1 anúncio/semana/usuário, até 2 imagens | `POST /charity-ads` |
| Urgência e caridade são gratuitos | sem cobrança nesses módulos |

## Autenticação

Todas as rotas de escrita exigem o header:

```
Authorization: Bearer <access_token>
```

O token é obtido em `POST /auth/register` ou `POST /auth/login`.
Admin é identificado pela flag `is_admin` no usuário **ou** por registro na tabela `admins`.

## Endpoints principais

| Módulo | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/verify-email`, `POST /auth/verify-phone`, `POST /auth/resend-phone-code`, `POST /auth/resend-verification-email` |
| Usuários | `GET /users/me`, `PUT /users/me` |
| Anúncios | `POST /ads`, `GET /ads`, `GET /ads/highlighted`, `GET /ads/mine`, `GET /ads/{id}`, `PUT /ads/{id}`, `DELETE /ads/{id}` |
| Avaliações | `POST /ads/{id}/reviews`, `GET /ads/{id}/reviews`, `DELETE /ads/{id}/reviews/{review_id}` |
| Grupos | `POST /groups`, `GET /groups`, `GET /groups/{id}`, `DELETE /groups/{id}` |
| Urgência | `POST /urgent-ads`, `GET /urgent-ads`, `GET /urgent-ads/{id}`, `DELETE /urgent-ads/{id}` |
| Caridade | `POST /charity-ads`, `GET /charity-ads`, `GET /charity-ads/{id}`, `DELETE /charity-ads/{id}` |
| Gift codes | `POST /gift-codes/redeem` |
| Denúncias | `POST /reports` |
| Pagamentos | `POST /payments/checkout`, `POST /payments/webhook`, `GET /payments/mine` |
| Ranking | `GET /ranking/latest` |
| Admin | `GET /admin/stats`, `GET/POST /admin/moderation/{kind}...`, `GET /admin/users`, `POST /admin/users/{id}/block`, `POST /admin/gift-codes`, `GET /admin/reports`, `POST /admin/reports/{id}/resolve`, `POST /admin/ranking/run`, `GET/PUT/DELETE /admin/tables/{table}[/{id}]` |

## Schema SQL de referência (Supabase)

Se alguma coluna ainda não existir nas suas tabelas, este script garante a
compatibilidade com o backend:

```sql
-- USERS
alter table users
  add column if not exists password_hash text,
  add column if not exists email_verified boolean default false,
  add column if not exists phone_verified boolean default false,
  add column if not exists email_verification_token text,
  add column if not exists phone_verification_code text,
  add column if not exists phone_code_expires_at timestamptz,
  add column if not exists referral_code text unique,
  add column if not exists referred_by uuid,
  add column if not exists is_admin boolean default false,
  add column if not exists is_blocked boolean default false,
  add column if not exists block_reason text,
  add column if not exists created_at timestamptz default now();

-- ADS
alter table ads
  add column if not exists website text,
  add column if not exists instagram text,
  add column if not exists facebook text,
  add column if not exists opening_hours text,
  add column if not exists image_url_2 text,
  add column if not exists status text default 'pending',
  add column if not exists is_highlighted boolean default false,
  add column if not exists highlight_until timestamptz,
  add column if not exists rejection_reason text,
  add column if not exists moderated_at timestamptz,
  add column if not exists deleted_at timestamptz,
  add column if not exists created_at timestamptz default now();

-- REVIEWS
alter table reviews
  add column if not exists created_at timestamptz default now();

-- GROUPS
alter table groups
  add column if not exists logo_url text,
  add column if not exists status text default 'pending',
  add column if not exists rejection_reason text,
  add column if not exists moderated_at timestamptz,
  add column if not exists created_at timestamptz default now();

-- URGENT_ADS
alter table urgent_ads
  add column if not exists document_url text,
  add column if not exists status text default 'pending',
  add column if not exists expires_at timestamptz,
  add column if not exists created_at timestamptz default now();

-- CHARITY_ADS
alter table charity_ads
  add column if not exists image_url_2 text,
  add column if not exists status text default 'pending',
  add column if not exists created_at timestamptz default now();

-- GIFT_CODES
alter table gift_codes
  add column if not exists type text default 'highlight',
  add column if not exists max_uses int default 1,
  add column if not exists uses_count int default 0,
  add column if not exists used_by uuid[] default '{}',
  add column if not exists used_at timestamptz,
  add column if not exists active boolean default true,
  add column if not exists expires_at timestamptz,
  add column if not exists created_by uuid,
  add column if not exists created_at timestamptz default now();

-- REPORTS
alter table reports
  add column if not exists status text default 'open',
  add column if not exists resolution_note text,
  add column if not exists resolved_at timestamptz,
  add column if not exists created_at timestamptz default now();

-- PAYMENTS
alter table payments
  add column if not exists stripe_session_id text,
  add column if not exists paid_at timestamptz,
  add column if not exists created_at timestamptz default now();

-- MONTHLY_RANKING
alter table monthly_ranking
  add column if not exists reward_granted boolean default false,
  add column if not exists created_at timestamptz default now();

-- EDIT_HISTORY
alter table edit_history
  add column if not exists created_at timestamptz default now();

-- Índices úteis
create index if not exists idx_ads_status_city on ads(status, city);
create index if not exists idx_ads_highlight on ads(is_highlighted, highlight_until);
create index if not exists idx_reviews_ad on reviews(ad_id);
create index if not exists idx_urgent_expiration on urgent_ads(status, expires_at);
create index if not exists idx_reports_status on reports(status);
create index if not exists idx_edit_history_month on edit_history(ad_id, created_at);
```

## Observações de produção

1. **RLS**: como o backend usa a `service_role` key (bypassa RLS) e faz a autorização
   no código via JWT próprio, mantenha a service key **somente no servidor**.
2. **Imagens**: uploads passam pelo backend → Cloudinary (máx. 10 MB; JPG/PNG/WebP;
   PDF aceito apenas para BO).
3. **Cron**: o scheduler roda dentro do processo do uvicorn. Em múltiplos workers,
   use um único worker para o scheduler ou um serviço externo (ex.: Supabase Cron).
4. **Secrets**: nunca versione o `.env`.
