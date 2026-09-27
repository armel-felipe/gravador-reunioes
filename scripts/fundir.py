"""Funde speakers da diarização por similaridade de voz (embeddings do pyannote).

Estratégia: para cada speaker, extrai o embedding médio de voz (até 20 segmentos
mais longos). Funde dois speakers apenas se a similaridade cosine entre os
embeddings for >= limiar (default 0.85) — sem heurística de duração/vizinhança,
evitando juntar pessoas diferentes por engano.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
import torchaudio

# PyTorch 2.6+ carrega checkpoints com weights_only=True por padrão;
# os checkpoints do pyannote contêm classes customizadas que precisam ser permitidas.
from pyannote.audio.core.task import Problem, Resolution, Specifications
from pyannote.audio.models.embedding import XVectorMFCC, XVectorSincNet
from pyannote.audio.models.segmentation import PyanNet

torch.serialization.add_safe_globals([
    torch.torch_version.TorchVersion,
    Specifications,
    Problem,
    Resolution,
    XVectorMFCC,
    XVectorSincNet,
    PyanNet,
])

from pyannote.audio.models.embedding import XVectorSincNet

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config, audio_paths

ROOT = Path(__file__).resolve().parent.parent


def carregar_token() -> str:
    """Lê o token do HuggingFace do .env do projeto (ou da env var)."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for linha in env_path.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha.startswith("HUGGINGFACE_TOKEN="):
                token = linha.split("=", 1)[1].strip().strip('"').strip("'")
                if token and token != "hf_cole_seu_token_aqui":
                    return token
    token = os.environ.get("HUGGINGFACE_TOKEN", "")
    if token:
        return token
    raise RuntimeError("Token do HuggingFace não encontrado (veja .env.example)")


def fundir_por_similaridade(embeddings: dict, por_speaker: dict, limiar: float) -> dict:
    """Fusão gulosa: speaker -> rótulo final, fundindo pares com similaridade >= limiar.

    embeddings: {speaker: vetor normalizado}
    por_speaker: {speaker: [segmentos]}
    Retorna: {speaker_original: speaker_final}
    """
    # Universo = todos os speakers da diarização; quem ficou sem embedding
    # (ex.: só falas < 0.5s) permanece com o próprio rótulo, sem quebrar.
    speakers = list(embeddings.keys())
    fundidos = {sp: sp for sp in por_speaker}
    for i in range(len(speakers)):
        for j in range(i + 1, len(speakers)):
            a, b = speakers[i], speakers[j]
            if fundidos[a] == fundidos[b]:
                continue
            sim = float(np.dot(embeddings[a], embeddings[b]))
            if sim >= limiar:
                # Funde no rótulo de quem fala mais (mais segmentos)
                alvo = a if len(por_speaker[a]) >= len(por_speaker[b]) else b
                origem = b if alvo == a else a
                for sp in speakers:
                    if fundidos[sp] == fundidos[origem]:
                        fundidos[sp] = fundidos[alvo]
    return fundidos


def re_rotular(diarizacao: list, fundidos: dict) -> list:
    """Re-rotula os speakers fundidos como SPEAKER_00, SPEAKER_01... na ordem de tempo de fala."""
    tempo_por_rotulo = {}
    for s in diarizacao:
        rotulo = fundidos[s["speaker"]]
        tempo_por_rotulo[rotulo] = tempo_por_rotulo.get(rotulo, 0) + (s["end"] - s["start"])
    ordem = sorted(tempo_por_rotulo, key=lambda r: -tempo_por_rotulo[r])
    mapa = {rotulo: f"SPEAKER_{i:02d}" for i, rotulo in enumerate(ordem)}
    return [dict(s, speaker=mapa[fundidos[s["speaker"]]]) for s in diarizacao]


def fundir_por_embedding(wav_path: str, diarizacao: list, token: str, limiar: float = 0.85) -> list:
    """Funde speakers com similaridade de voz >= limiar. Retorna a diarização fundida."""
    if len({s["speaker"] for s in diarizacao}) <= 1:
        return diarizacao

    waveform, sample_rate = torchaudio.load(wav_path)
    modelo = XVectorSincNet.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=token)
    modelo.eval()

    # Agrupa segmentos por speaker
    por_speaker = {}
    for s in diarizacao:
        por_speaker.setdefault(s["speaker"], []).append(s)

    # Embedding médio por speaker (até 20 segmentos mais longos, >= 0.5s)
    embeddings = {}
    with torch.no_grad():
        for speaker, segs in por_speaker.items():
            segs_ordenados = sorted(segs, key=lambda s: s["end"] - s["start"], reverse=True)[:20]
            embs = []
            for s in segs_ordenados:
                if s["end"] - s["start"] < 0.5:
                    continue
                try:
                    inicio = int(s["start"] * sample_rate)
                    fim = int(s["end"] * sample_rate)
                    trecho = waveform[:, inicio:fim].unsqueeze(0)  # (1, 1, samples)
                    if trecho.shape[-1] < sample_rate // 2:  # < 0.5s
                        continue
                    emb = modelo(trecho)
                    embs.append(emb.squeeze(0).cpu().numpy())
                except Exception:
                    continue
            if embs:
                embeddings[speaker] = np.mean(embs, axis=0)
                embeddings[speaker] /= np.linalg.norm(embeddings[speaker])

    if len(embeddings) <= 1:
        return diarizacao

    fundidos = fundir_por_similaridade(embeddings, por_speaker, limiar)
    return re_rotular(diarizacao, fundidos)


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    token = carregar_token()
    with open(paths["diarizacao_json"], encoding="utf-8") as f:
        diarizacao = json.load(f)
    limiar = cfg.get("diarizacao", {}).get("limiar_fusao", 0.85)
    antes = len({s["speaker"] for s in diarizacao})
    fundida = fundir_por_embedding(str(paths["wav"]), diarizacao, token, limiar=limiar)
    depois = len({s["speaker"] for s in fundida})
    with open(paths["diarizacao_fundida_json"], "w", encoding="utf-8") as f:
        json.dump(fundida, f, ensure_ascii=False, indent=2)
    print(f"Fusão: {antes} → {depois} speakers (limiar {limiar}) → {paths['diarizacao_fundida_json']}")


if __name__ == "__main__":
    main(sys.argv[1])
