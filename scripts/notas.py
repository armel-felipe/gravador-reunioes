"""Gera notas (resumo + plano de ação) via LLM local/cloud, com map-reduce."""
import os
import re
import uuid
import time
import hashlib
from pathlib import Path

import requests
from dotenv import load_dotenv

from common import load_config, audio_paths

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)

# Configuração do map-reduce (em minutos)
BLOCO_MINUTOS = 10
OVERLAP_MINUTOS = 2
REDUCE_GRUPO = 2

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
    llm = cfg.get("llm") or {}
    provider = llm.get("active")
    profiles = llm.get("providers") or {}
    profile = profiles.get(provider)
    if not provider or not profile:
        disponiveis = ", ".join(profiles) or "nenhum"
        raise RuntimeError(
            f"perfil LLM inválido: {provider!r} (use um de: {disponiveis})"
        )

    tipo = profile.get("type")
    model = profile.get("model")
    if not model:
        raise RuntimeError(f"modelo não configurado no perfil LLM {provider!r}")

    if tipo == "ollama":
        url = profile.get("base_url", "http://localhost:11434").rstrip("/") + "/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        headers = {}
    elif tipo == "openai":
        url = profile["base_url"].rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if "max_tokens" in profile:
            payload["max_tokens"] = profile["max_tokens"]
        if "reasoning_effort" in profile:
            # Campo aceito pelo endpoint OpenAI-compatible do Ollama Cloud.
            payload["reasoning_effort"] = profile["reasoning_effort"]
        headers = {}
        env_name = profile.get("api_key_env")
        if env_name:
            api_key = os.environ.get(env_name, "")
            if not api_key:
                raise RuntimeError(f"API key não configurada — defina a env var {env_name}")
            headers["Authorization"] = f"Bearer {api_key}"
    else:
        raise RuntimeError(f"tipo de perfil LLM inválido: {tipo!r}")

    tentativas = profile.get("retries", 1)
    for tentativa in range(tentativas):
        resp = requests.post(url, json=payload, headers=headers, timeout=600)
        resp.raise_for_status()
        if tipo == "openai":
            content = resp.json()["choices"][0]["message"].get("content", "").strip()
            if content:
                return content
            if tentativa + 1 < tentativas:
                time.sleep(min(2 ** tentativa, 8))
                continue
            raise RuntimeError("modelo retornou conteúdo vazio para as notas")
        return resp.json()["response"]
    raise RuntimeError("não foi possível gerar notas")


def _id_checkpoint(cfg: dict, transcricao: str) -> str:
    llm = cfg.get("llm") or {}
    provider = llm.get("active", "")
    model = (llm.get("providers") or {}).get(provider, {}).get("model", provider)
    material = "|".join(("v1", provider, model, PROMPT_MAP, REGRAS_QUALIDADE, transcricao))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _chamar_reduce_com_checkpoint(cfg: dict, resumos: list, checkpoint: Path = None) -> str:
    if checkpoint is not None and checkpoint.exists():
        resumo = checkpoint.read_text(encoding="utf-8").strip()
        if resumo:
            return resumo
    prompt = montar_prompt_reduce("\n\n---\n\n".join(resumos))
    resumo = chamar_ollama(cfg, prompt)
    if checkpoint is not None:
        temporario = checkpoint.with_suffix(".tmp")
        temporario.write_text(resumo + "\n", encoding="utf-8")
        temporario.replace(checkpoint)
    return resumo


def gerar_notas_map_reduce(cfg: dict, transcricao: str, checkpoint_dir: Path = None) -> str:
    """Map-reduce: divide em blocos, resume cada um, consolida no final."""
    blocos = dividir_em_blocos(transcricao)
    if len(blocos) <= 1:
        # Reunião curta — prompt único (comportamento original)
        return chamar_ollama(cfg, montar_prompt(transcricao))

    pasta_checkpoint = None
    if checkpoint_dir is not None:
        pasta_checkpoint = Path(checkpoint_dir) / f"notas_map_{_id_checkpoint(cfg, transcricao)}"
        pasta_checkpoint.mkdir(parents=True, exist_ok=True)

    print(f"Map-reduce: {len(blocos)} blocos de ~{BLOCO_MINUTOS} min (overlap {OVERLAP_MINUTOS} min)")
    resumos = []
    for i, bloco in enumerate(blocos, 1):
        checkpoint = pasta_checkpoint / f"map_{i:02d}.md" if pasta_checkpoint else None
        resumo = checkpoint.read_text(encoding="utf-8").strip() if checkpoint and checkpoint.exists() else ""
        if resumo:
            print(f"  Map {i}/{len(blocos)} — checkpoint reutilizado")
        else:
            print(f"  Map {i}/{len(blocos)}...")
            prompt = montar_prompt_map(bloco, i, len(blocos))
            resumo = chamar_ollama(cfg, prompt)
            if checkpoint:
                temporario = checkpoint.with_suffix(".tmp")
                temporario.write_text(resumo + "\n", encoding="utf-8")
                temporario.replace(checkpoint)
        resumos.append(resumo)

    if len(resumos) <= REDUCE_GRUPO:
        print("  Reduce: consolidando...")
        checkpoint = pasta_checkpoint / "reduce_final.md" if pasta_checkpoint else None
        return _chamar_reduce_com_checkpoint(cfg, resumos, checkpoint)

    print(f"  Reduce: consolidando em grupos de até {REDUCE_GRUPO}...")
    parciais = resumos
    nivel = 1
    while len(parciais) > REDUCE_GRUPO:
        grupos = [parciais[i:i + REDUCE_GRUPO] for i in range(0, len(parciais), REDUCE_GRUPO)]
        proximos = []
        for i, grupo in enumerate(grupos, 1):
            nome = "reduce_grupo" if nivel == 1 else f"reduce_nivel_{nivel}"
            checkpoint = pasta_checkpoint / f"{nome}_{i:02d}.md" if pasta_checkpoint else None
            proximos.append(_chamar_reduce_com_checkpoint(cfg, grupo, checkpoint))
        parciais = proximos
        nivel += 1

    print("  Reduce final: consolidando grupos...")
    checkpoint = pasta_checkpoint / "reduce_final.md" if pasta_checkpoint else None
    return _chamar_reduce_com_checkpoint(cfg, parciais, checkpoint)


def _write_notes_atomic(destination: Path, text: str) -> None:
    if not text.strip():
        raise ValueError("notas vazias não podem marcar o evento como processado")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main(nome_base: str, model_override: str = None):
    cfg = load_config()
    if model_override:
        if not model_override.strip() or len(model_override) > 256 or any(ord(character) < 32 for character in model_override):
            raise ValueError("identificador de modelo inválido")
        active = cfg.get("llm", {}).get("active")
        profiles = cfg.get("llm", {}).get("providers", {})
        profile = profiles.get(active)
        if not profile:
            raise ValueError(f"perfil LLM ativo inválido: {active!r}")
        profile["model"] = model_override
    paths = audio_paths(nome_base)
    transcricao = paths["transcricao_md"].read_text(encoding="utf-8")
    texto = gerar_notas_map_reduce(cfg, transcricao, checkpoint_dir=paths["transcricao_md"].parent / "_tmp")
    destino = paths["notas_md"]
    _write_notes_atomic(destino, f"# Notas — {nome_base}\n\n{texto}\n")
    print(f"Notas → {destino}")
