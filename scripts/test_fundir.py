"""Testes da fusão de speakers (fundir.py)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fundir import fundir_por_similaridade, re_rotular


def _vetor(orientacao: str) -> np.ndarray:
    v = {"x": [1.0, 0.0], "y": [0.0, 1.0]}[orientacao]
    v = np.array(v)
    return v / np.linalg.norm(v)


def test_fusao_basica_mantem_speakers_distintos():
    diarizacao = [
        {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
        {"start": 3.0, "end": 5.0, "speaker": "SPEAKER_01"},
    ]
    embeddings = {"SPEAKER_00": _vetor("x"), "SPEAKER_01": _vetor("y")}
    por_speaker = {sp: [s for s in diarizacao if s["speaker"] == sp] for sp in embeddings}
    fundidos = fundir_por_similaridade(embeddings, por_speaker, limiar=0.85)
    resultado = re_rotular(diarizacao, fundidos)
    assert {s["speaker"] for s in resultado} == {"SPEAKER_00", "SPEAKER_01"}


def test_speaker_sem_embedding_nao_quebra_re_rotular():
    """Speaker com só segmentos curtos (<0.5s) não ganha embedding, mas existe
    na diarização — re_rotular não pode dar KeyError (bug real do evento
    2026_09_26_10_03_hub_imersivo_skills, SPEAKER_04 com 2 falas de 0.4s)."""
    diarizacao = [
        {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
        {"start": 3.0, "end": 5.0, "speaker": "SPEAKER_01"},
        {"start": 6.0, "end": 6.3, "speaker": "SPEAKER_04"},  # sem embedding
    ]
    embeddings = {"SPEAKER_00": _vetor("x"), "SPEAKER_01": _vetor("y")}
    por_speaker = {sp: [s for s in diarizacao if s["speaker"] == sp] for sp in {s["speaker"] for s in diarizacao}}
    fundidos = fundir_por_similaridade(embeddings, por_speaker, limiar=0.85)
    resultado = re_rotular(diarizacao, fundidos)
    assert len(resultado) == 3
    assert resultado[2]["speaker"] in {"SPEAKER_00", "SPEAKER_01", "SPEAKER_02"}
