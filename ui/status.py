"""Reusable single-slot status messages for Streamlit pages."""
from __future__ import annotations

import streamlit as st


def create_status_slot(key: str):
    """Create one replaceable message area and render a pending flash message."""
    slot = st.empty()
    pending = st.session_state.pop(key, None)
    if pending:
        render_status(slot, pending["level"], pending["message"])
    return slot


def render_status(slot, level: str, message: str) -> None:
    """Replace the previous status instead of stacking another message box."""
    slot.empty()
    renderer = getattr(slot, level, None)
    if renderer is None or level not in {"success", "info", "warning", "error"}:
        raise ValueError(f"Unsupported status level: {level}")
    renderer(message)


def flash_status(key: str, level: str, message: str) -> None:
    """Persist one status across st.rerun() and replace any previous notice."""
    if level not in {"success", "info", "warning", "error"}:
        raise ValueError(f"Unsupported status level: {level}")
    st.session_state[key] = {"level": level, "message": message}
