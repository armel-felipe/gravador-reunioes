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
    return PROMPT.format(transcricao=transcricao)


def chamar_ollama(cfg: dict, prompt: str) -> str:
    provider = cfg["ollama"]["provider"]
    if provider == "local":
        url = "http://localhost:11434/api/generate"
        model = cfg["ollama"]["local_model"]
        payload = {"model": model, "prompt": prompt, "stream": False}
    else:
        url = cfg["ollama"]["cloud_base_url"].rstrip("/") + "/generate"
        model = cfg["ollama"]["cloud_model"]
        api_key = os.environ.get(cfg["ollama"]["cloud_api_key_env"], "")
        payload = {"model": model, "prompt": prompt, "stream": False}
        headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.post(url, json=payload, headers=headers if provider == "cloud" else {}, timeout=600)
    resp.raise_for_status()
    return resp.json()["response"]


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    transcricao = paths["transcricao_md"].read_text(encoding="utf-8")
    prompt = montar_prompt(transcricao)
    texto = chamar_ollama(cfg, prompt)
    notas_dir = Path(cfg["caminhos"]["notas_dir"])
    notas_dir.mkdir(parents=True, exist_ok=True)
    destino = notas_dir / f"{nome_base}.md"
    destino.write_text(f"# Notas — {nome_base}\n\n{texto}\n", encoding="utf-8")
    print(f"Notas → {destino}")
