"""Gera notas (resumo + plano de ação) via Ollama."""
import os
from pathlib import Path

import requests

from common import load_config, audio_paths

PROMPT = """Você é um assistente que transforma transcrições de reuniões em notas estruturadas em português.

Transcrição:
{transcricao}

Gere:
1. **Resumo executivo** (máx. 150 palavras)
2. **Tópicos principais** (lista)
3. **Decisões tomadas** (lista; se não houver, diga "Nenhuma decisão explícita")
4. **Plano de ação** (tabela: Ação | Responsável | Prazo — use "—" quando não citado)

Formato: Markdown limpo, sem introdução nem conclusão."""


def montar_prompt(transcricao: str) -> str:
    return PROMPT.replace("{transcricao}", transcricao)


def chamar_ollama(cfg: dict, prompt: str) -> str:
    provider = cfg["ollama"]["provider"]
    if provider == "local":
        url = "http://localhost:11434/api/generate"
        model = cfg["ollama"]["local_model"]
        payload = {"model": model, "prompt": prompt, "stream": False}
        headers = {}
    elif provider == "cloud":
        base_url = cfg["ollama"]["cloud_base_url"].rstrip("/")
        url = base_url + "/v1/chat/completions"
        model = cfg["ollama"]["cloud_model"]
        env_name = cfg["ollama"]["cloud_api_key_env"]
        api_key = os.environ.get(env_name, "")
        if not api_key:
            raise RuntimeError(f"API key não configurada — defina a env var {env_name}")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        raise RuntimeError(f"provider inválido: {provider!r} (use 'local' ou 'cloud')")
    resp = requests.post(url, json=payload, headers=headers, timeout=600)
    resp.raise_for_status()
    if provider == "cloud":
        return resp.json()["choices"][0]["message"]["content"]
    return resp.json()["response"]


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    transcricao = paths["transcricao_md"].read_text(encoding="utf-8")
    prompt = montar_prompt(transcricao)
    texto = chamar_ollama(cfg, prompt)
    destino = paths["notas_md"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(f"# Notas — {nome_base}\n\n{texto}\n", encoding="utf-8")
    print(f"Notas → {destino}")
