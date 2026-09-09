"""Lógica de alinhamento transcrição × diarização (importável e testável)."""


def alinhar_falas(transcricao: list, diarizacao: list) -> list:
    falas = []
    for fala in transcricao:
        speaker = "Desconhecido"
        melhor_sobreposicao = 0.0
        for seg in diarizacao:
            inicio = max(fala["start"], seg["start"])
            fim = min(fala["end"], seg["end"])
            sobreposicao = max(0.0, fim - inicio)
            if sobreposicao > melhor_sobreposicao:
                melhor_sobreposicao = sobreposicao
                speaker = seg["speaker"]
        falas.append({**fala, "speaker": speaker})
    return falas
