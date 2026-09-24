# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

"""
Servidor principal del agente de WhatsApp.
Funciona con cualquier proveedor (Meta, Twilio) gracias a la capa de providers.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import (
    inicializar_db,
    guardar_mensaje,
    obtener_historial,
    mensaje_ya_procesado,
    marcar_mensaje_procesado,
)
from agent.providers import obtener_proveedor

load_dotenv()

# Configuración de logging según entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

# Proveedor de WhatsApp (se configura en .env con WHATSAPP_PROVIDER)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar el servidor."""
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="AgentKit — WhatsApp AI Agent (Inmobiliaria)",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway/monitoreo."""
    return {"status": "ok", "service": "agentkit"}


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    """Verificación GET del webhook (requerido por Meta Cloud API, no-op para otros)."""
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


async def _procesar_mensaje(telefono: str, texto: str):
    """
    Genera y envía la respuesta a un mensaje ya validado y marcado como
    procesado. Corre como background task — el webhook ya le respondió
    200 OK al proveedor antes de que esto empiece, así que Gemini puede
    tardar lo que tarde sin arriesgar que 360dialog/Meta reintenten la
    entrega del webhook por timeout.
    """
    try:
        historial = await obtener_historial(telefono)
        respuesta = await generar_respuesta(texto, historial, telefono)

        await guardar_mensaje(telefono, "user", texto)
        await guardar_mensaje(telefono, "assistant", respuesta)

        enviado = await proveedor.enviar_mensaje(telefono, respuesta)
        if not enviado:
            logger.error(f"No se pudo entregar la respuesta a {telefono}")

        logger.info(f"Respuesta a {telefono}: {respuesta}")
    except Exception as e:
        logger.error(f"Error procesando mensaje de {telefono}: {e}")


@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """
    Recibe mensajes de WhatsApp via el proveedor configurado.
    Valida y encola el procesamiento en background, respondiendo 200 de
    inmediato — así el proveedor nunca ve el webhook "colgado" mientras
    Gemini genera la respuesta y no reintenta la entrega del mismo mensaje.
    """
    try:
        # Verificar que el POST realmente venga del proveedor (firma HMAC).
        # Sin esto, cualquiera que descubra la URL podría hacer que el
        # agente gaste tokens de Claude respondiendo mensajes falsos.
        if not await proveedor.validar_autenticidad(request):
            logger.warning("Webhook rechazado: firma inválida o ausente")
            raise HTTPException(status_code=403, detail="Firma inválida")

        # Parsear webhook — el proveedor normaliza el formato
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            # Ignorar mensajes propios o vacíos
            if msg.es_propio or not msg.texto:
                continue

            # Idempotencia: Meta y Twilio pueden reintentar la entrega del
            # mismo webhook (timeouts, reintentos automáticos). Sin este
            # chequeo, el mismo mensaje se procesaría y respondería 2+ veces.
            if await mensaje_ya_procesado(msg.mensaje_id):
                logger.info(f"Mensaje {msg.mensaje_id} ya procesado — se ignora reintento")
                continue
            await marcar_mensaje_procesado(msg.mensaje_id)

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")
            if os.getenv("VERCEL"):
                # Serverless: la función se congela al devolver la respuesta,
                # así que hay que terminar de procesar antes de responder.
                await _procesar_mensaje(msg.telefono, msg.texto)
            else:
                background_tasks.add_task(_procesar_mensaje, msg.telefono, msg.texto)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
