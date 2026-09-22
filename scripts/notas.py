"""Gera notas (resumo + plano de ação) via Ollama, com map-reduce para reuniões longas."""
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

from common import load_config, audio_paths

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)

# Configuração do map-reduce (em minutos)
BLOCO_MINUTOS = 10
OVERLAP_MINUTOS = 2

REGRAS_QUALIDADE = """Regras de qualidade:
- Preserve nomes, empresas, números, datas e decisões presentes no texto, além de exemplos, instituições, valores e referências.
- Mantenha todos os tópicos discutidos, mesmo que pareçam secundários; agrupe apenas quando falarem do mesmo assunto.
- Dê contexto suficiente para que cada tópico seja entendido por alguém que não ouviu a reunião: explique o ponto levantado, os motivos, exemplos, consequências e relações mencionados no texto, sem repetir a transcrição inteira.
- Não invente informações nem transforme hipótese em fato.
- Registre decisões, ações, responsáveis e prazos somente quando estiverem explicitamente confirmados no texto. Sugestões, possibilidades, recomendações didáticas e assuntos a investigar não são ações ou decisões tomadas.
- Não corrija, complete ou substitua nomes próprios, siglas, termos técnicos ou conceitos que pareçam erro do reconhecimento de voz. Preserve a forma transcrita e, se a incerteza for relevante, marque [termo incerto na transcrição].
- "Conciso" significa eliminar redundância e repetição, não omitir detalhe relevante."""

PROMPT = """Você é um assistente que transforma transcrições de reuniões em notas estruturadas em português.

Transcrição:
{transcricao}

{regras}

Gere:
1. **Resumo executivo** (máx. 250 palavras)
2. **Tópicos principais** (lista)
3. **Decisões tomadas** (lista; se não houver, diga "Nenhuma decisão explícita")
4. **Plano de ação** (tabela: Ação | Responsável | Prazo — use "—" quando não citado)

Formato: Markdown limpo, sem introdução nem conclusão."""

PROMPT_MAP = """Você é um assistente que transforma um TRECHO de transcrição de reunião em notas estruturadas em português.

Trecho (parte {indice} de {total}):
{trecho}

{regras}

Gere:
1. **Resumo do trecho** (máx. 200 palavras)
2. **Tópicos principais** (lista)
3. **Decisões tomadas** (lista; se não houver, diga "Nenhuma decisão explícita")
4. **Plano de ação** (tabela: Ação | Responsável | Prazo — use "—" quando não citado)

Formato: Markdown limpo, sem introdução nem conclusão."""

PROMPT_REDUCE = """Você é um assistente que consolida resumos parciais de uma reunião em notas finais em português.

Resumos parciais (cada um cobre um trecho da reunião, com sobreposição de 2 min entre trechos):
{resumos}

{regras}

Consolide em:
1. **Resumo executivo** (máx. 350 palavras) — visão geral da reunião inteira
2. **Tópicos principais** (lista consolidada, sem duplicatas)
3. **Decisões tomadas** (lista consolidada; se não houver, diga "Nenhuma decisão explícita")
4. **Plano de ação** (tabela: Ação | Responsável | Prazo — use "—" quando não citado)

Regras:
- Cruze referências entre os trechos: se um tópico aparece em vários, consolide em um só.
- Não invente informações que não estejam nos resumos.
- Formato: Markdown limpo, sem introdução nem conclusão."""


def montar_prompt(transcricao: str) -> str:
    return PROMPT.replace("{transcricao}", transcricao).replace("{regras}", REGRAS_QUALIDADE)


def montar_prompt_map(trecho: str, indice: int, total: int) -> str:
    return (
        PROMPT_MAP.replace("{trecho}", trecho)
        .replace("{indice}", str(indice))
        .replace("{total}", str(total))
        .replace("{regras}", REGRAS_QUALIDADE)
    )


def montar_prompt_reduce(resumos: str) -> str:
    return PROMPT_REDUCE.replace("{resumos}", resumos).replace("{regras}", REGRAS_QUALIDADE)


def dividir_em_blocos(transcricao: str, bloco_min: int = BLOCO_MINUTOS, overlap_min: int = OVERLAP_MINUTOS) -> list:
    """Divide a transcrição diarizada em blocos por tempo, com sobreposição.

    A transcrição tem linhas no formato:
      **[MM:SS] SPEAKER_XX:** texto
    (ou **[H:MM:SS]** para reuniões longas). Cada bloco cobre bloco_min minutos,
    com overlap_min minutos de sobreposição com o bloco anterior.
    """
    linhas = transcricao.splitlines()
    if not linhas:
        return []

    # Extrai (timestamp_em_segundos, linha) de cada fala
    falas = []
    for linha in linhas:
        m = re.match(r"^\*\*\[(\d+):(\d+):(\d+)\]\s+", linha)
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            falas.append((h * 3600 + mi * 60 + s, linha))
        else:
            # linha sem timestamp (ex.: cabeçalho) — anexa à fala anterior
            if falas:
                falas[-1] = (falas[-1][0], falas[-1][1] + "\n" + linha)

    if not falas:
        return [transcricao]

    duracao_total = falas[-1][0]
    bloco_seg = bloco_min * 60
    overlap_seg = overlap_min * 60

    # Reunião curta (ou sem timestamps): um único bloco com tudo
    if duracao_total <= bloco_seg:
        return ["\n".join(l for _, l in falas)]

    # Gera os intervalos de blocos
    blocos = []
    inicio = 0
    while inicio < duracao_total:
        fim = inicio + bloco_seg
        blocos.append((inicio, fim))
        if fim >= duracao_total:
            break
        inicio = fim - overlap_seg

    # Monta o texto de cada bloco
    resultado = []
    for i, (b_inicio, b_fim) in enumerate(blocos):
        linhas_bloco = [l for t, l in falas if b_inicio <= t < b_fim]
        if linhas_bloco:
            resultado.append("\n".join(linhas_bloco))
    return resultado


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


def gerar_notas_map_reduce(cfg: dict, transcricao: str) -> str:
    """Map-reduce: divide em blocos, resume cada um, consolida no final."""
    blocos = dividir_em_blocos(transcricao)
    if len(blocos) <= 1:
        # Reunião curta — prompt único (comportamento original)
        return chamar_ollama(cfg, montar_prompt(transcricao))

    print(f"Map-reduce: {len(blocos)} blocos de ~{BLOCO_MINUTOS} min (overlap {OVERLAP_MINUTOS} min)")
    resumos = []
    for i, bloco in enumerate(blocos, 1):
        print(f"  Map {i}/{len(blocos)}...")
        prompt = montar_prompt_map(bloco, i, len(blocos))
        resumos.append(chamar_ollama(cfg, prompt))

    print("  Reduce: consolidando...")
    prompt = montar_prompt_reduce("\n\n---\n\n".join(resumos))
    return chamar_ollama(cfg, prompt)


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    transcricao = paths["transcricao_md"].read_text(encoding="utf-8")
    texto = gerar_notas_map_reduce(cfg, transcricao)
    destino = paths["notas_md"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(f"# Notas — {nome_base}\n\n{texto}\n", encoding="utf-8")
    print(f"Notas → {destino}")
