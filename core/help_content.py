"""Contenido del FAQ / Ayuda embebido en la app."""

HELP_SECTIONS = [
    {
        "title": "¿Qué hace esta app?",
        "content": """
Prospector Web busca negocios locales en Google Maps que no tienen página web o la tienen desactualizada,
les genera una landing de muestra y te arma el mensaje de WhatsApp listo para enviar.

**Flujo completo:**
1. Buscas negocios en una zona → la app calcula quién es mejor prospecto
2. Guardas los que te interesan como clientes
3. Generas el prompt → lo pegas en claude.ai → descargas el HTML
4. La app publica la landing en Netlify (link público automático)
5. Das click en "Abrir WhatsApp" → el mensaje con precio y link ya viene escrito
6. Marcas como enviado → sigues el seguimiento desde "Mis clientes"
""",
    },
    {
        "title": "¿Cómo arrancar la app?",
        "content": """
**Opción A — Icono en el escritorio (recomendada)**
- Doble clic en **"Prospector Web"** en el escritorio
- Espera ~15 segundos → el navegador se abre solo en `http://localhost:8501`
- La ventana negra que aparece es normal — es el servidor. No la cierres.

**Opción B — Terminal**
```
cd "...ruta del proyecto..."
streamlit run app.py
```
""",
    },
    {
        "title": "¿Cómo buscar prospectos?",
        "content": """
1. En el **sidebar izquierdo**: escribe la zona (ej. "Naucalpan, EDOMEX"), ajusta el radio y elige la categoría
2. Selecciona el **Filtro inteligente** — "Top prospects" es el recomendado
3. Click en **Buscar prospectos**
4. Usa los **Filtros locales** (arriba de la tabla) para afinar: score mínimo, solo sin web, solo con email, etc.
5. Da click en **💾 Guardar** en los que quieras trabajar (o usa "Guardar en lote" para varios a la vez)

**Score 1–10:** mientras más alto mejor. 8–10 (verde) son prioridad. Toma en cuenta si tienen web, rating, reseñas y categoría.
""",
    },
    {
        "title": "¿Cómo generar una landing y mandar WhatsApp?",
        "content": """
1. Ve a **👥 Mis clientes** → selecciona el cliente
2. Sub-pestaña **📋 Prompt para Claude** → copia el texto
3. Abre **claude.ai** en otra pestaña → pega el prompt → espera la respuesta
4. En claude.ai: descarga el HTML (botón de descarga arriba a la derecha del código)
5. Regresa a la app → sub-pestaña **📥 Cargar HTML** → sube el archivo
6. Sección **💬 Mensaje WhatsApp**:
   - Elige la plantilla ("Inicial sin web" para primer contacto)
   - Pega la URL de Netlify si ya la tienes, o deja vacío por ahora
   - Click **📲 Abrir WhatsApp con mensaje** → se abre WhatsApp Web con el mensaje listo
   - Revisa, ajusta si quieres, y da **Enviar** en WhatsApp
7. De vuelta en la app → click **✅ Marcar como enviado**
""",
    },
    {
        "title": "¿Qué es Netlify y cómo publicar la landing?",
        "content": """
**Netlify** es el servicio donde se publica la landing para que el cliente pueda verla desde su celular.
Es gratuito y ya está configurado.

**Opción A — Automático (desde Automatización masiva)**
- La app sube el HTML y te devuelve el link automáticamente

**Opción B — Manual (30 segundos)**
1. Ve a https://app.netlify.com/drop en otra pestaña
2. Arrastra el archivo `.html` que descargaste de claude.ai
3. Netlify te da un link tipo `https://nombre.netlify.app`
4. Pega ese link en el campo "URL Netlify" de la app

Ese link es lo que mandas al cliente en WhatsApp para que vea la demo.
""",
    },
    {
        "title": "¿Qué hace la pestaña Automatización?",
        "content": """
Sirve para procesar **muchos clientes de un jalón**.

**Fase A — Los que ya tienen landing:**
1. Sube el Excel exportado → click "Importar"
2. Ajusta filtros (score, estado, categoría)
3. Click "Iniciar pipeline" → publica todas las landings en Netlify + arma todos los mensajes WhatsApp
4. Aparece la lista de listos → das click en "Enviar" uno por uno

**Fase B — Los que no tienen landing:**
- La app te los muestra con su prompt
- Generas el HTML en claude.ai y lo subes
- Luego vuelves a correr Fase A

**Importante:** necesitas haber cargado el HTML de la landing a cada cliente antes de que Fase A lo procese.
""",
    },
    {
        "title": "¿Cómo exportar a Excel o PDF?",
        "content": """
**Excel:**
- Pestaña **📤 Exportar** → "Exportar a Excel"
- El archivo tiene 3 hojas: Prospectos (con todos los datos), Prompts para Claude (listo para copiar), Resumen

**PDF de propuesta:**
- En **👥 Mis clientes** → sección PDF → "Generar PDF"
- Es una hoja A4 imprimible con datos del negocio, propuesta de valor y tus datos de contacto
- Útil para visitas presenciales

Los archivos se guardan en la carpeta `outputs/` junto al ejecutable.
""",
    },
    {
        "title": "¿Cómo dar seguimiento a los clientes?",
        "content": """
En **👥 Mis clientes**, cada cliente tiene:

- **Estado** (pipeline): Pendiente → Mensaje enviado → Respondió → Llamada/visita → Propuesta enviada → Negociación → Cerrado
- **Próximo contacto**: fecha para hacer follow-up
- **Precio cotizado**: cuánto le dijiste
- **Notas**: campo libre para escribir lo que pasó en cada contacto

**Tip:** después de cada interacción actualiza el estado y escribe una nota corta. Cuando vuelvas a abrir la app sabes exactamente dónde quedaste con cada uno.
""",
    },
    {
        "title": "Algo no funciona, ¿qué hago?",
        "content": """
**La app no abre:**
- Cierra la ventana negra si está abierta y vuelve a hacer doble clic al icono
- Si sigue sin abrir, abre una terminal y corre `streamlit run app.py`

**"No encontró negocios":**
- Verifica que la zona esté bien escrita (ej. "Coyoacán, CDMX" no "coyoacan")
- Cambia el filtro a "Todos" para ver si hay resultados sin filtrar
- Aumenta el radio de búsqueda

**El mensaje de WhatsApp no abre:**
- Verifica que el número del cliente tenga 10 dígitos
- Asegúrate de tener WhatsApp Web abierto en el navegador

**Error al subir HTML:**
- El archivo debe ser el `.html` descargado directo de claude.ai
- No debe estar dentro de una carpeta zip

**Contacto:**
Gilberto Rayo — RAIO Development
55 4117 7890 · raio-agency.support@gmail.com
""",
    },
]
