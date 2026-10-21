# Design: limpeza segura de áudios processados

## Objetivo

Impedir que a rotina de retenção remova áudio de uma gravação que ainda não foi processada.

## Regra

Um evento só pode ter sua pasta `audio/` removida quando:

1. o WAV mais recente do evento exceder o limite configurado; e
2. existir `notas/<evento>.md`, o marcador oficial de processamento concluído.

Eventos antigos sem esse arquivo permanecem intactos para poderem ser processados depois.

## Implementação e validação

- Adicionar teste para evento antigo sem nota: o áudio deve permanecer e nenhum arquivo deve ser listado como apagado.
- Manter os testes existentes para evento antigo processado e para preservação de transcrições/notas.
- Alterar apenas a lógica de elegibilidade em `scripts/limpar.py`.
- Executar os testes específicos e a suíte documentada do projeto.
