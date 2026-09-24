# agent/providers/dialog360.py — Adaptador para el Sandbox de 360dialog
# Generado por AgentKit

"""
360dialog es un BSP (partner oficial de Meta) que expone el WhatsApp
Business Cloud API por su cuenta, con un Sandbox de prueba que no
requiere pasar por developers.facebook.com (evita el registro de
developer de Meta, que puede fallar en el paso de verificación por SMS).

El formato de mensajes es casi idéntico al de Meta Cloud API directo:
  - Autenticación por header D360-API-KEY en vez de Bearer token
  - El payload del webhook entrante llega ANIDADO igual que Meta directo
    (entry -> changes -> value -> messages) — confirmado contra el
    sandbox real, la documentación pública de 360dialog lo describe
    como plano pero en la práctica no lo es
  - El webhook se configura con una llamada a la API, no hay pantalla
    de configuración en ningún dashboard
"""

import os
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")

BASE_URL = "https://waba-sandbox.360dialog.io"


class ProveedorDialog360(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando el Sandbox de 360dialog."""

    def __init__(self):
        self.api_key = os.getenv("D360_API_KEY")

    async def validar_autenticidad(self, request: Request) -> bool:
        """
        El Sandbox de 360dialog no documenta un mecanismo de firma para
        webhooks entrantes (a diferencia de Meta/Twilio). Se acepta sin
        validar SOLO porque es un sandbox de prueba — antes de usar esto
        en producción, confirmar con 360dialog si su plan pago sí firma
        los webhooks y agregar la validación correspondiente acá.
        """
        if not self.api_key:
            logger.error("D360_API_KEY no configurado")
            return False
        return True

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """Parsea el payload anidado de 360dialog (mismo shape que Meta Cloud API)."""
        body = await request.json()
        mensajes = []
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    if msg.get("type") == "text":
                        mensajes.append(MensajeEntrante(
                            telefono=msg.get("from", ""),
                            texto=msg.get("text", {}).get("body", ""),
                            mensaje_id=msg.get("id", ""),
                            es_propio=False,
                        ))
        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envía mensaje via la API de 360dialog."""
        if not self.api_key:
            logger.warning("D360_API_KEY no configurado")
            return False
        url = f"{BASE_URL}/v1/messages"
        headers = {"D360-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "text",
            "text": {"body": mensaje},
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code != 200:
                logger.error(f"Error 360dialog: {r.status_code} — {r.text}")
            return r.status_code == 200
