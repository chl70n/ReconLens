"""
client.py — Ollama local LLM wrapper

HTTP POST to localhost:11434/api/generate via requests.
No API keys. No SDK. No data leaves the machine.

Ollama request schema:
  { model, prompt, system, stream: false }

Ollama response schema:
  { "response": "<text>", "done": true, ... }
"""

import requests

from config import LOCAL_MODEL_NAME, OLLAMA_GENERATE_URL, SYSTEM_INSTRUCTION
from parser import payload_to_json


def query_ollama(payload: dict) -> str:
    """
    Send compressed Nmap payload to local Ollama and return analysis.

    Args:
        payload: Output of parser.parse_nmap_xml() — {"hosts": [...]}

    Returns:
        Markdown-formatted vulnerability analysis string.

    Raises:
        RuntimeError: Ollama unreachable, HTTP error, or timeout.
    """
    json_payload = payload_to_json(payload)
    prompt = (
        "Analyze these Nmap scan results and identify security vulnerabilities:\n\n"
        f"{json_payload}"
    )

    body = {
        "model": LOCAL_MODEL_NAME,
        "prompt": prompt,
        "system": SYSTEM_INSTRUCTION,
        "stream": False,
    }

    try:
        response = requests.post(
            OLLAMA_GENERATE_URL,
            json=body,
            timeout=120,  # local models can be slow on first load
        )
        response.raise_for_status()

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot reach Ollama at http://localhost:11434.\n"
            "  → Ensure Ollama is running: `ollama serve`\n"
            "  → Ensure model is pulled: `ollama pull llama3.2`"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Ollama request timed out after 120s.\n"
            "  → Model may still be loading. Retry in a moment."
        )
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"Ollama HTTP error {response.status_code}: {exc}") from exc

    data = response.json()
    return data.get("response", "").strip()
