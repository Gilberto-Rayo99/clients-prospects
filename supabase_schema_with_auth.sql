-- Prospector Web — Schema endurecido con Supabase Auth + RLS por owner
--
-- ⚠️ NO ejecutes esto sobre una DB con datos sin antes hacer backup y
-- backfillear `owner_id` en las filas existentes. Mira los pasos al final.
--
-- Cuándo aplicar:
--   - Cuando estés listo para pasar de SUPABASE_SERVICE_KEY a ANON_KEY + auth.
--   - Reduce el blast radius si filtras la key: con ANON_KEY sola NO se puede
--     leer/escribir nada sin sesión auth válida.
--
-- Antes de aplicar:
--   1. Crear un usuario en Supabase Dashboard → Authentication → Users
--      (email + password). Anota el UUID que te dé.
--   2. Backup de la tabla:
--        SELECT * FROM clients;  -- exporta a CSV desde el dashboard
--   3. Si ya tienes filas, backfill primero:
--        ALTER TABLE clients ADD COLUMN owner_id UUID;
--        UPDATE clients SET owner_id = '<TU_UUID_AQUI>'::UUID WHERE owner_id IS NULL;
--        ALTER TABLE clients ALTER COLUMN owner_id SET NOT NULL;
--      Luego aplicar el resto.

-- 1) Columna de propietario (vincula la fila al usuario auth)
ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS owner_id UUID NOT NULL DEFAULT auth.uid();

CREATE INDEX IF NOT EXISTS idx_clients_owner_id ON clients(owner_id);

-- 2) Asegurar RLS activado (ya lo está, idempotente)
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

-- 3) Policies: cada usuario solo ve/edita SUS filas
DROP POLICY IF EXISTS "owner_select" ON clients;
CREATE POLICY "owner_select" ON clients
  FOR SELECT USING (auth.uid() = owner_id);

DROP POLICY IF EXISTS "owner_insert" ON clients;
CREATE POLICY "owner_insert" ON clients
  FOR INSERT WITH CHECK (auth.uid() = owner_id);

DROP POLICY IF EXISTS "owner_update" ON clients;
CREATE POLICY "owner_update" ON clients
  FOR UPDATE USING (auth.uid() = owner_id) WITH CHECK (auth.uid() = owner_id);

DROP POLICY IF EXISTS "owner_delete" ON clients;
CREATE POLICY "owner_delete" ON clients
  FOR DELETE USING (auth.uid() = owner_id);

-- 4) Después de aplicar:
--    - En el cliente Python, sustituir SUPABASE_SERVICE_KEY por SUPABASE_ANON_KEY
--    - Añadir login Supabase Auth: supabase.auth.sign_in_with_password({email, password})
--    - El cliente debe persistir la sesión en st.session_state y refrescar token
--    - Borrar (o ROTAR) la SERVICE_KEY desde Supabase Dashboard
