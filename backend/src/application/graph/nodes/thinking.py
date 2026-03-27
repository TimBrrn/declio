from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from backend.src.application.graph.state import CallState
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.ports.conversation_port import ConversationPort, ToolCall
from backend.src.domain.value_objects.token_usage import TokenUsage

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts"

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Reserve un rendez-vous pour le patient",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_hint": {
                        "type": "string",
                        "description": "Date souhaitee par le patient (ex: 'lundi prochain', 'demain matin')",
                    },
                },
                "required": ["date_hint"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Annule un rendez-vous existant du patient",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Nom du patient dont on annule le RDV",
                    },
                    "date_hint": {
                        "type": "string",
                        "description": "Date du RDV a annuler (ex: 'jeudi', 'le 15')",
                    },
                },
                "required": ["patient_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Consulte les creneaux disponibles du cabinet",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_hint": {
                        "type": "string",
                        "description": "Periode souhaitee (ex: 'cette semaine', 'lundi')",
                    },
                },
                "required": ["date_hint"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_booking",
            "description": (
                "Confirme la reservation d'un creneau choisi par le patient. "
                "A appeler apres que le patient a choisi un creneau parmi ceux proposes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_index": {
                        "type": "integer",
                        "description": "Numero du creneau choisi (1, 2, 3...)",
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Nom complet du patient",
                    },
                },
                "required": ["slot_index", "patient_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leave_message",
            "description": "Prend un message pour le kinesitherapeute",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Le message a transmettre",
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Nom du patient",
                    },
                    "patient_phone": {
                        "type": "string",
                        "description": "Numero de telephone du patient",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_conversation",
            "description": (
                "Signale la fin naturelle de la conversation. "
                "Appeler quand le patient dit au revoir ou n'a plus de question."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def _format_horaires(horaires: dict[str, list[str]]) -> str:
    """Formate les horaires du cabinet pour le prompt."""
    lines = []
    for jour, plages in horaires.items():
        lines.append(f"  {jour} : {', '.join(plages)}")
    return "\n".join(lines) if lines else "  Non renseignes"


def _format_montant(montant: float) -> str:
    """Formate un montant en euros avec centimes si necessaire."""
    euros = int(montant)
    centimes = round((montant - euros) * 100)
    if centimes:
        return f"{euros} euros {centimes:02d} centimes"
    return f"{euros} euros"


def _format_tarifs(tarifs: dict[str, float]) -> str:
    """Formate les tarifs du cabinet pour le prompt."""
    lines = []
    for type_soin, montant in tarifs.items():
        lines.append(f"  {type_soin} : {_format_montant(montant)}")
    return "\n".join(lines) if lines else "  Non renseignes"


def _load_system_prompt(cabinet: Cabinet) -> str:
    """Charge et enrichit le system prompt avec les donnees du cabinet."""
    prompt_path = PROMPTS_DIR / "system_prompt.md"
    if prompt_path.exists():
        template = prompt_path.read_text(encoding="utf-8")
    else:
        template = (
            "Tu es l'assistante virtuelle du cabinet {nom_cabinet}. "
            "Tu reponds aux appels telephoniques."
        )

    # Remplacer les placeholders
    text = template.replace("{nom_cabinet}", cabinet.nom_cabinet)
    text = text.replace("{nom_praticien}", cabinet.nom_praticien)
    text = text.replace("{adresse}", cabinet.adresse)
    text = text.replace("{horaires}", _format_horaires(cabinet.horaires))
    text = text.replace("{tarifs}", _format_tarifs(cabinet.tarifs))

    # Tarif exemple pour le few-shot
    if cabinet.tarifs:
        first_tarif = next(iter(cabinet.tarifs.values()))
        text = text.replace("{tarif_exemple}", _format_montant(first_tarif))
    else:
        text = text.replace("{tarif_exemple}", "tarif non renseigne")

    # Ajouter les prompts de scenarios
    for scenario_file in ("booking.md", "cancellation.md", "faq.md"):
        scenario_path = PROMPTS_DIR / "scenarios" / scenario_file
        if scenario_path.exists():
            text += "\n\n" + scenario_path.read_text(encoding="utf-8")

    return text


def _convert_messages(messages: list) -> list[dict[str, Any]]:
    """Convertit les BaseMessage LangChain en format dict OpenAI."""
    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.type == "ai":
            entry: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content,
            }
            # Propager les tool_calls stockes dans additional_kwargs
            tc = msg.additional_kwargs.get("tool_calls")
            if tc:
                entry["tool_calls"] = tc
                # OpenAI exige content=null quand il y a des tool_calls sans texte
                if not msg.content:
                    entry["content"] = None
            result.append(entry)
        elif msg.type == "tool":
            result.append({
                "role": "tool",
                "content": msg.content,
                "tool_call_id": getattr(msg, "tool_call_id", ""),
            })
        else:
            result.append({"role": "user", "content": msg.content})
    return result


async def thinking_node(
    state: CallState,
    conversation: ConversationPort,
) -> dict:
    """Analyse la transcription via le LLM. Decide : repondre ou appeler un tool."""
    cabinet = state["cabinet"]
    messages = state.get("messages", [])

    system_prompt = _load_system_prompt(cabinet)

    # Construire les messages pour le LLM
    llm_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    llm_messages.extend(_convert_messages(messages))

    logger.info("Thinking node: sending %d messages to LLM", len(llm_messages))
    t0 = time.perf_counter()

    response_text, tool_calls, token_usage = await conversation.chat_with_tools(
        messages=llm_messages,
        tools=TOOLS_SCHEMA,
    )

    latency_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "LLM response: latency_ms=%.0f tokens=%d cost_usd=%.6f",
        latency_ms,
        token_usage.total_tokens,
        token_usage.cost_usd,
    )

    if tool_calls:
        tool_names = [tc.name for tc in tool_calls]
        logger.info("LLM requested %d tool_calls: %s", len(tool_calls), tool_names)
    if response_text:
        logger.debug("LLM response text: %.200s", response_text)

    new_messages = list(messages)

    # Construire l'AIMessage avec les tool_calls au format LangChain
    if tool_calls:
        # Stocker les tool_calls dans additional_kwargs pour que
        # le prochain tour puisse les envoyer au LLM
        tc_openai_format = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": _serialize_arguments(tc.arguments),
                },
            }
            for tc in tool_calls
        ]
        new_messages.append(
            AIMessage(
                content=response_text or "",
                additional_kwargs={"tool_calls": tc_openai_format},
            )
        )
    elif response_text:
        new_messages.append(AIMessage(content=response_text))

    # Detecter end_conversation tool call
    should_hangup = state.get("should_hangup", False)
    non_end_tool_calls: list[ToolCall] = []
    for tc in tool_calls:
        if tc.name == "end_conversation":
            should_hangup = True
            logger.info("end_conversation detected, will hangup")
        else:
            non_end_tool_calls.append(tc)

    # Extraire le nom du patient des tool_calls
    patient_name = state.get("patient_name")
    for tc in tool_calls:
        name = tc.arguments.get("patient_name")
        if name:
            patient_name = name
            logger.info("Patient name extracted: %s", patient_name)

    # Accumulate per-turn token data
    existing_turns = list(state.get("token_turns") or [])
    tool_name = "+".join(tc.name for tc in tool_calls) if tool_calls else None
    existing_turns.append({
        "turn_index": len(existing_turns),
        "prompt_tokens": token_usage.prompt_tokens,
        "completion_tokens": token_usage.completion_tokens,
        "total_tokens": token_usage.total_tokens,
        "cost_usd": token_usage.cost_usd,
        "model": token_usage.model,
        "tool_name": tool_name,
    })

    return {
        "messages": new_messages,
        "response_text": response_text,
        "pending_tool_calls": non_end_tool_calls,
        "should_hangup": should_hangup,
        "patient_name": patient_name,
        "token_turns": existing_turns,
    }


def _serialize_arguments(args: dict[str, Any]) -> str:
    """Serialize arguments dict to JSON string for OpenAI format."""
    return json.dumps(args, ensure_ascii=False)
