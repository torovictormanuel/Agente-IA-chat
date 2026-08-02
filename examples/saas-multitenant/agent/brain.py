# agent/brain.py — Cerebro del agente: Gemini + tool calling (multi-tenant)
# Generado por AgentKit

"""
Motor genérico de conversación + tool-calling. A diferencia del modo
single-tenant (que importaba TOOLS/EJECUTAR_TOOL fijos de agent.tools),
acá TODO lo específico del negocio llega por parámetro: el system prompt,
las tools disponibles y su dispatcher. Este archivo no sabe qué negocio
ni qué rubro está atendiendo — eso lo resuelve main.py antes de llamarlo.

Usa la Interactions API de Gemini (client.interactions.create). El
historial de conversación lo manejamos nosotros en SQLite (memory.py),
así que cada llamada es "stateless" del lado de Google: store=False y
reenviamos todo el historial acumulado como `input` en cada request.
"""

import os
import json
import logging
from typing import Callable, Awaitable
from google import genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Verificá el nombre exacto disponible en tu cuenta en aistudio.google.com —
# Google libera modelos nuevos seguido y los nombres/versiones cambian.
MODELO = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
MAX_TURNOS_TOOL = 5


def _tools_a_gemini(tools: list[dict]) -> list[dict] | None:
    """
    Convierte TOOLS (formato name/description/input_schema) a function
    declarations de Gemini (name/description/parameters). El JSON Schema
    de adentro es compatible tal cual.
    """
    if not tools:
        return None
    return [
        {
            "type": "function",
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        }
        for t in tools
    ]


def _historial_a_input(historial: list[dict]) -> list[dict]:
    """Convierte [{"role": "user"/"assistant", "content": str}] al formato
    de steps que espera `input` en la Interactions API."""
    pasos = []
    for m in historial:
        tipo = "user_input" if m["role"] == "user" else "model_output"
        pasos.append({"type": tipo, "content": [{"type": "text", "text": m["content"]}]})
    return pasos


async def _ejecutar_tool(
    nombre: str,
    argumentos: dict,
    telefono: str,
    negocio_id: str,
    ejecutar_tool: dict[str, Callable[..., Awaitable[dict]]],
) -> dict:
    """
    `telefono` y `negocio_id` se inyectan SIEMPRE — el modelo nunca los ve
    ni los puede falsificar. Así se garantiza que una tool jamás pueda
    operar sobre el número o los datos de otro negocio.
    """
    funcion = ejecutar_tool.get(nombre)
    if not funcion:
        return {"error": f"Herramienta '{nombre}' no existe"}
    try:
        return await funcion(telefono=telefono, negocio_id=negocio_id, **argumentos)
    except Exception as e:
        logger.error(f"Error ejecutando tool '{nombre}' (negocio={negocio_id}): {e}")
        return {"error": str(e)}


async def generar_respuesta(
    mensaje: str,
    historial: list[dict],
    telefono: str,
    negocio_id: str,
    system_prompt: str,
    tools: list[dict],
    ejecutar_tool: dict[str, Callable[..., Awaitable[dict]]],
    fallback_message: str = "Disculpa, no entendí tu mensaje. ¿Podrías reformularlo?",
    error_message: str = "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo en unos minutos.",
) -> str:
    """
    Genera una respuesta para UN negocio específico, resolviendo tool
    calls si el modelo las solicita.
    """
    if not mensaje or len(mensaje.strip()) < 2:
        return fallback_message

    tools_gemini = _tools_a_gemini(tools)
    entrada = _historial_a_input(historial) + [
        {"type": "user_input", "content": [{"type": "text", "text": mensaje}]}
    ]

    try:
        for _ in range(MAX_TURNOS_TOOL):
            interaction = await client.aio.interactions.create(
                model=MODELO,
                system_instruction=system_prompt,
                input=entrada,
                store=False,
                tools=tools_gemini,
            )

            if interaction.status != "requires_action":
                logger.info(f"Respuesta generada (negocio={negocio_id}, status={interaction.status})")
                return interaction.output_text or fallback_message

            llamadas = [s for s in interaction.steps if s.type == "function_call"]
            for step in interaction.steps:
                entrada.append(step.model_dump())

            for llamada in llamadas:
                logger.info(f"Tool call (negocio={negocio_id}): {llamada.name}({llamada.arguments})")
                resultado = await _ejecutar_tool(llamada.name, llamada.arguments, telefono, negocio_id, ejecutar_tool)
                entrada.append({
                    "type": "function_result",
                    "call_id": llamada.id,
                    "name": llamada.name,
                    "result": [{"type": "text", "text": json.dumps(resultado, ensure_ascii=False, default=str)}],
                })

        logger.warning(f"Límite de turnos de tool-calling alcanzado (negocio={negocio_id})")
        return error_message

    except Exception as e:
        logger.error(f"Error Gemini API (negocio={negocio_id}): {e}")
        return error_message
