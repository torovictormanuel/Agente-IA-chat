# agent/brain.py — Cerebro del agente: conexión con Gemini + tool calling
# Generado por AgentKit

"""
Lógica de IA del agente. Lee el system prompt de prompts.yaml, ofrece al
modelo las herramientas definidas en tools.py (TOOLS/EJECUTAR_TOOL) y
resuelve el loop de tool-calling hasta obtener una respuesta de texto final.

Usa la Interactions API de Gemini (client.interactions.create), la forma
recomendada actual del SDK google-genai. Como el historial de conversación
lo manejamos nosotros mismos en SQLite (memory.py), cada llamada es
"stateless" del lado de Google: store=False y reenviamos todo el
historial acumulado como `input` en cada request — Google no retiene
nada entre mensajes.

Este archivo es genérico: no sabe nada de inmobiliaria específicamente.
Para adaptar a otro rubro, se reescribe agent/tools.py, no este archivo.
"""

import os
import json
import yaml
import logging
from google import genai
from dotenv import load_dotenv

from agent.tools import TOOLS, EJECUTAR_TOOL

load_dotenv()
logger = logging.getLogger("agentkit")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Verificá el nombre exacto disponible en tu cuenta en aistudio.google.com —
# Google libera modelos nuevos seguido y los nombres/versiones cambian.
MODELO = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
MAX_TURNOS_TOOL = 5  # límite de idas y vueltas modelo <-> herramientas por mensaje


def cargar_config_prompts() -> dict:
    """Lee toda la configuración desde config/prompts.yaml."""
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def cargar_system_prompt() -> str:
    """Lee el system prompt desde config/prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("system_prompt", "Eres un asistente útil. Responde en español.")


def obtener_mensaje_error() -> str:
    """Retorna el mensaje de error configurado en prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo en unos minutos.")


def obtener_mensaje_fallback() -> str:
    """Retorna el mensaje de fallback configurado en prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpa, no entendí tu mensaje. ¿Podrías reformularlo?")


def _tools_a_gemini(tools: list[dict]) -> list[dict] | None:
    """
    Convierte TOOLS (formato name/description/input_schema, el mismo que
    usa la API de Anthropic) a function declarations de Gemini
    (name/description/parameters). El JSON Schema de adentro es
    compatible tal cual — no hace falta tocar tools.py al cambiar de LLM.
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
    """
    Convierte [{"role": "user"/"assistant", "content": str}] (formato en
    el que memory.py guarda todo) al formato de steps que espera el
    parámetro `input` de la Interactions API.
    """
    pasos = []
    for m in historial:
        tipo = "user_input" if m["role"] == "user" else "model_output"
        pasos.append({"type": tipo, "content": [{"type": "text", "text": m["content"]}]})
    return pasos


async def _ejecutar_tool(nombre: str, argumentos: dict, telefono: str) -> dict:
    """
    Ejecuta una función de tools.py y retorna su resultado.

    `telefono` se inyecta SIEMPRE como kwarg — el modelo nunca lo ve ni
    lo puede inventar, así se evita que alguien le pida al agente actuar
    sobre el número de teléfono de otra persona.
    """
    funcion = EJECUTAR_TOOL.get(nombre)
    if not funcion:
        return {"error": f"Herramienta '{nombre}' no existe"}
    try:
        return await funcion(telefono=telefono, **argumentos)
    except Exception as e:
        logger.error(f"Error ejecutando tool '{nombre}': {e}")
        return {"error": str(e)}


async def generar_respuesta(mensaje: str, historial: list[dict], telefono: str) -> str:
    """
    Genera una respuesta usando Gemini, resolviendo tool calls si el
    modelo las solicita (buscar propiedades, agendar visitas, etc.).

    Args:
        mensaje: el mensaje nuevo del usuario
        historial: mensajes previos [{"role": "user/assistant", "content": "..."}]
        telefono: número del cliente — se inyecta a las tools, nunca lo maneja el modelo

    Returns:
        La respuesta final en texto para enviar por WhatsApp
    """
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = cargar_system_prompt()
    tools_gemini = _tools_a_gemini(TOOLS)
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
                logger.info(f"Respuesta generada (status={interaction.status})")
                return interaction.output_text or obtener_mensaje_fallback()

            # El modelo pidió usar una o más herramientas antes de responder.
            # Reinyectamos los steps que generó (incluye los function_call)
            # y después agregamos el resultado de cada una como input nuevo.
            llamadas = [s for s in interaction.steps if s.type == "function_call"]
            for step in interaction.steps:
                entrada.append(step.model_dump())

            for llamada in llamadas:
                logger.info(f"Tool call: {llamada.name}({llamada.arguments})")
                resultado = await _ejecutar_tool(llamada.name, llamada.arguments, telefono)
                entrada.append({
                    "type": "function_result",
                    "call_id": llamada.id,
                    "name": llamada.name,
                    "result": [{"type": "text", "text": json.dumps(resultado, ensure_ascii=False, default=str)}],
                })

        # Se agotaron los turnos de tool-calling sin llegar a una respuesta final
        logger.warning("Límite de turnos de tool-calling alcanzado sin respuesta final")
        return obtener_mensaje_error()

    except Exception as e:
        logger.error(f"Error Gemini API: {e}")
        return obtener_mensaje_error()
