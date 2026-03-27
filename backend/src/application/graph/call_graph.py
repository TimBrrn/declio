"""LangGraph StateGraph — orchestre la conversation telephonique.

Graphe :
    GREETING → LISTENING → THINKING
    THINKING → TOOL_EXEC (si tool call) → THINKING (resultat tool)
    THINKING → RESPONDING (si reponse directe)
    RESPONDING → LISTENING (conversation continue)
    RESPONDING → HANGUP (fin detectee)
    HANGUP → SUMMARY → END
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

from backend.src.application.graph.nodes.greeting import greeting_node
from backend.src.application.graph.nodes.listening import listening_node
from backend.src.application.graph.nodes.responding import responding_node
from backend.src.application.graph.nodes.summary import summary_node
from backend.src.application.graph.nodes.thinking import thinking_node
from backend.src.application.graph.nodes.tool_exec import tool_exec_node
from backend.src.application.graph.state import CallState
from backend.src.domain.ports.calendar_port import CalendarPort
from backend.src.domain.ports.conversation_port import ConversationPort
from backend.src.domain.ports.notification_port import NotificationPort

# Node names
GREETING = "greeting"
LISTENING = "listening"
THINKING = "thinking"
TOOL_EXEC = "tool_exec"
RESPONDING = "responding"
HANGUP = "hangup"
SUMMARY = "summary"


def _route_after_thinking(state: CallState) -> str:
    """Route conditionnel apres THINKING : tool_exec ou responding."""
    pending = state.get("pending_tool_calls", [])
    if pending:
        tool_names = [tc.name for tc in pending]
        logger.info("Route THINKING -> TOOL_EXEC (tools=%s)", tool_names)
        return TOOL_EXEC
    logger.info("Route THINKING -> RESPONDING")
    return RESPONDING


def _route_after_responding(state: CallState) -> str:
    """Route conditionnel apres RESPONDING : listening ou hangup."""
    if state.get("should_hangup", False):
        logger.info("Route RESPONDING -> HANGUP")
        return HANGUP
    logger.debug("Route RESPONDING -> LISTENING")
    return LISTENING


def _hangup_node(state: CallState) -> dict:
    """Noeud HANGUP — marque la fin de conversation."""
    return {"should_hangup": True}


def build_call_graph(
    conversation: ConversationPort,
    calendar: CalendarPort,
    notification: NotificationPort,
) -> Any:
    """Construit et compile le graphe conversationnel."""
    graph = StateGraph(CallState)

    # Ajouter les noeuds
    graph.add_node(GREETING, greeting_node)
    graph.add_node(LISTENING, listening_node)
    graph.add_node(
        THINKING,
        partial(thinking_node, conversation=conversation),
    )
    graph.add_node(
        TOOL_EXEC,
        partial(tool_exec_node, calendar=calendar),
    )
    graph.add_node(RESPONDING, responding_node)
    graph.add_node(HANGUP, _hangup_node)
    graph.add_node(
        SUMMARY,
        partial(summary_node, notification=notification),
    )

    # Transitions
    graph.set_entry_point(GREETING)
    graph.add_edge(GREETING, LISTENING)
    graph.add_edge(LISTENING, THINKING)

    graph.add_conditional_edges(
        THINKING,
        _route_after_thinking,
        {TOOL_EXEC: TOOL_EXEC, RESPONDING: RESPONDING},
    )

    graph.add_edge(TOOL_EXEC, THINKING)

    graph.add_conditional_edges(
        RESPONDING,
        _route_after_responding,
        {LISTENING: LISTENING, HANGUP: HANGUP},
    )

    graph.add_edge(HANGUP, SUMMARY)
    graph.add_edge(SUMMARY, END)

    return graph.compile()
