-- Prospector Web — Schema Supabase
-- Ejecuta este SQL en: Supabase Dashboard → SQL Editor → New query

CREATE TABLE IF NOT EXISTS clients (
  id                   TEXT PRIMARY KEY,
  fecha_guardado       TEXT,
  fecha_modificado     TEXT,

  -- Datos del negocio
  name                 TEXT NOT NULL DEFAULT '',
  category             TEXT DEFAULT '',
  address              TEXT DEFAULT '',
  phone                TEXT,
  email                TEXT,
  website              TEXT,
  rating               NUMERIC,
  reviews_count        INTEGER DEFAULT 0,
  place_id             TEXT,
  lat                  NUMERIC,
  lng                  NUMERIC,
  maps_url             TEXT,
  social_links         JSONB DEFAULT '{}',

  -- Calculados
  score                INTEGER,
  contact_channel      TEXT,
  contact_value        TEXT,

  -- Landing
  landing_html         TEXT,
  landing_path         TEXT,
  netlify_url          TEXT,
  netlify_site_id      TEXT,
  netlify_deploy_at    TEXT,

  -- Seguimiento
  estado               TEXT DEFAULT 'Pendiente',
  notas                TEXT DEFAULT '',
  fecha_proximo_contacto TEXT,
  precio_cotizado      NUMERIC,
  pdf_path             TEXT
);

-- RLS activado (solo service_role puede acceder — las llaves anon no tienen acceso)
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- Tabla key-value para estado pequeño que debe sobrevivir reboots
-- (cuota Gemini, flags, etc.). Usada por core/app_kv.py.
-- ============================================================
CREATE TABLE IF NOT EXISTS app_kv (
  key        TEXT PRIMARY KEY,
  value      JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE app_kv ENABLE ROW LEVEL SECURITY;
