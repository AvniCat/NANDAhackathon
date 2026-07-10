"""LLM abstraction — Gemini primary, Ollama fallback. Reused pattern."""
from __future__ import annotations
import os
from typing import Iterable
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
OLLAMA_HOST     = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_CHAT     = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:3b")
LLM_MODE        = os.getenv("LLM_MODE", "primary").lower()


class LLMError(RuntimeError):
    pass


def _gemini_chat(prompt: str, system: str | None, json_mode: bool = False) -> str:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    kwargs = {"system_instruction": system} if system else {}
    if json_mode:
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"},
            **kwargs,
        )
    else:
        model = genai.GenerativeModel(GEMINI_MODEL, **kwargs)
    resp = model.generate_content(prompt)
    return resp.text


def _ollama_chat(prompt: str, system: str | None, json_mode: bool = False) -> str:
    import ollama
    client = ollama.Client(host=OLLAMA_HOST)
    messages = []
    if system: messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    kwargs = {"format": "json"} if json_mode else {}
    resp = client.chat(model=OLLAMA_CHAT, messages=messages, **kwargs)
    return resp["message"]["content"]


def chat(prompt: str, system: str | None = None, json_mode: bool = False) -> str:
    """Gemini primary, Ollama fallback. Set json_mode=True for constrained JSON output."""
    tried = []
    if LLM_MODE != "local" and GEMINI_API_KEY:
        try:
            return _gemini_chat(prompt, system, json_mode)
        except Exception as e:
            tried.append(f"Gemini: {type(e).__name__}: {e}")
    try:
        return _ollama_chat(prompt, system, json_mode)
    except Exception as e:
        tried.append(f"Ollama: {type(e).__name__}: {e}")
    raise LLMError("All providers failed:\n  " + "\n  ".join(tried))


def provider_status() -> dict:
    return {
        "gemini_configured": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL if GEMINI_API_KEY else None,
        "ollama_host": OLLAMA_HOST,
        "ollama_chat_model": OLLAMA_CHAT,
        "mode": LLM_MODE,
    }
