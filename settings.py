"""
settings.py — where the app finds its keys and passwords.

Render has no secrets.toml. Its settings are environment variables. My Codespace
and Streamlit Cloud use .streamlit/secrets.toml. So the environment is read
first, and secrets.toml only after it.

st.secrets does not return empty when there is no secrets.toml: reading it in
any way raises StreamlitSecretNotFoundError, and the page dies. Every read of
it goes through here so that can't happen again.
"""
import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


def secret(name, env=None):
    """One setting: the environment variable first (Render), then secrets.toml.
    Empty string when neither has it."""
    value = os.environ.get(env or name, "")
    if value:
        return value
    try:
        return st.secrets.get(name, "") or ""
    except StreamlitSecretNotFoundError:
        return ""


def all_secrets():
    """The whole of secrets.toml, for community.py's storage settings.
    An empty dict when there is no secrets.toml."""
    try:
        return dict(st.secrets)
    except StreamlitSecretNotFoundError:
        return {}
