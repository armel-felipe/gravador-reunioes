import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alinhar import alinhar_falas


def test_alinhar_falas_basico():
    transcricao = [
        {"start": 0.0, "end": 2.0, "text": "Bom dia"},
        {"start": 2.5, "end": 4.0, "text": "Vamos começar"},
    ]
    diarizacao = [
        {"start": 0.0, "end": 3.0, "speaker": "Falante 1"},
        {"start": 3.0, "end": 5.0, "speaker": "Falante 2"},
    ]
    falas = alinhar_falas(transcricao, diarizacao)
    assert falas[0]["speaker"] == "Falante 1"
    assert falas[1]["speaker"] == "Falante 2"


def test_alinhar_falas_sem_sobreposicao():
    transcricao = [{"start": 10.0, "end": 11.0, "text": "oi"}]
    diarizacao = [{"start": 0.0, "end": 5.0, "speaker": "Falante 1"}]
    falas = alinhar_falas(transcricao, diarizacao)
    assert falas[0]["speaker"] == "Desconhecido"
