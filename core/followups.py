"""Identifica clientes que necesitan follow-up — la tarea más alta-ROI del día.

Reglas de oro:
- "Mensaje enviado" + ≥7 días sin actividad → mandar follow_up_sin_respuesta
- "Llamada/visita" + ≥3 días → falta enviar la propuesta formal
- "Propuesta enviada" + ≥5 días → checar dudas, empujar al cierre
- "Negociación" + ≥3 días → cierre
- `fecha_proximo_contacto <= hoy` → recordatorio explícito (alta prioridad)

Devuelve clientes ordenados por urgencia (recordatorios primero, luego
los más viejos).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional


# (estado_actual, días_sin_actividad, motivo_humano, plantilla_sugerida)
FOLLOWUP_RULES: list[tuple[str, int, str, Optional[str]]] = [
    ("Mensaje enviado",   7, "Sin respuesta tras 7 días",                 "follow_up_sin_respuesta"),
    ("Llamada/visita",    3, "Tras la visita — falta enviar propuesta",   "post_llamada_propuesta"),
    ("Propuesta enviada", 5, "5 días con propuesta — checa dudas",        None),
    ("Negociación",       3, "3 días en negociación — empuja cierre",     None),
    ("Respondió",         3, "Respondió hace 3+ días — cierra la cita",   None),
]


def _days_since(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(iso)
    except Exception:
        return None
    return (datetime.now() - ts).days


def get_pending(clients: list[dict]) -> list[dict]:
    """Devuelve la lista de clientes que necesitan follow-up.

    Cada item es el dict del cliente + campos extra:
      - reason: str — motivo human-readable
      - days: int — días sin actividad
      - template: Optional[str] — plantilla WhatsApp sugerida
      - priority: int — 1 (recordatorio agendado), 2 (urgente), 3 (rezagado)

    Los estados terminales (Descartado, Cerrado, Sin teléfono) se excluyen
    aunque tengan fecha_proximo_contacto vencida — no tiene sentido
    recordarte de un cliente que ya dijo no.
    """
    import config

    pending: list[dict] = []
    today = date.today()

    for c in clients:
        # Saltar terminales — no requieren follow-up
        if c.get("estado") in config.INACTIVE_STATUSES:
            continue

        # 1) Recordatorio explícito (fecha_proximo_contacto vencida)
        prox_iso = c.get("fecha_proximo_contacto")
        if prox_iso:
            try:
                prox = date.fromisoformat(prox_iso)
                if prox <= today:
                    overdue = (today - prox).days
                    pending.append({
                        **c,
                        "reason": (
                            f"📅 Recordatorio agendado para {prox_iso}"
                            + (f" (atrasado {overdue}d)" if overdue > 0 else " (hoy)")
                        ),
                        "days": _days_since(c.get("fecha_modificado")) or 0,
                        "template": None,
                        "priority": 1,
                    })
                    continue  # no doble-contar con regla de estado
            except Exception:
                pass

        # 2) Reglas por estado + tiempo en ese estado
        estado = c.get("estado")
        for rule_estado, dias, motivo, tpl in FOLLOWUP_RULES:
            if estado != rule_estado:
                continue
            since = _days_since(c.get("fecha_modificado"))
            if since is None or since < dias:
                continue
            # Prioridad: 2 si está en rango "esperado", 3 si lleva más del doble
            prio = 3 if since >= dias * 2 else 2
            pending.append({
                **c,
                "reason": f"{motivo} ({since}d)",
                "days": since,
                "template": tpl,
                "priority": prio,
            })
            break

    # Orden: prioridad asc, luego más días primero
    pending.sort(key=lambda x: (x["priority"], -x["days"]))
    return pending


def summary_counts(pending: list[dict]) -> dict:
    """Cuenta por prioridad para mostrar en el banner."""
    return {
        "total": len(pending),
        "agendados": sum(1 for p in pending if p["priority"] == 1),
        "urgentes": sum(1 for p in pending if p["priority"] == 2),
        "rezagados": sum(1 for p in pending if p["priority"] == 3),
    }
