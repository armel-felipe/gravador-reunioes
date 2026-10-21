# Perfil llama.cpp para geração de notas — desenho

**Data:** 2026-10-13
**Status:** aprovado para especificação; aguardando revisão do documento antes da implementação.

## Contexto

O pipeline gera notas em `scripts/notas.py` usando o perfil selecionado em `llm.active`, definido em `config.yaml`. Perfis `type: openai` já usam o endpoint compatível com OpenAI `/chat/completions`, incluindo o perfil atual de LM Studio. A geração de notas e o map-reduce não devem depender de um provedor específico.

## Objetivo

Adicionar llama.cpp como provedor padrão para geração de notas, mantendo a possibilidade de selecionar qualquer modelo servido no endpoint ao solicitar a troca de modelo.

## Desenho aprovado

- Adicionar um perfil chamado `llama-cpp`, com `type: openai`.
- Usar `http://100.87.71.48:18080/v1` como `base_url` e `gemma-4-26b-a4b-it-q4_k_m` como `model` inicial.
- Tornar `llama-cpp` o perfil ativo padrão em `config.yaml`.
- Manter como modelos alternativos disponíveis para troca sob demanda:
  - `qwen3.5-35b-a3b-q4_k_m`
  - `qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-compact`
- Não adicionar autenticação ou variáveis de ambiente sem evidência de que o servidor exige isso.
- Preservar integralmente os prompts, o fluxo map-reduce, os checkpoints e os demais provedores. A chamada OpenAI-compatível existente deve ser reutilizada.

## Fluxo e erros

`llm.active` escolhe o perfil `llama-cpp`; a função existente envia o modelo e o prompt ao endpoint `/chat/completions`. Falhas de conexão, respostas HTTP inválidas ou resposta vazia devem continuar sendo tratadas pelo comportamento de erro já existente, sem fallback silencioso para outro servidor ou modelo.

Quando o usuário pedir outro modelo, a seleção deve atualizar somente o modelo escolhido para aquela execução, preservando o comportamento de configuração já usado para troca sob demanda. Não se deve presumir que os nomes listados correspondem a IDs diferentes sem consultar o endpoint do servidor; a implementação deve passar exatamente o ID solicitado.

## Documentação e testes

- Atualizar README e mapa para documentar o perfil padrão, URL base, os modelos disponíveis e como pedir a troca.
- Adicionar/ajustar testes de `scripts/notas.py` que confirmem a URL e o nome de modelo enviados no payload OpenAI-compatível para `llama-cpp`.
- Rodar os testes de notas e, em seguida, a suíte Python documentada do projeto.
- Não exigir conexão real ao servidor para testes automatizados; usar resposta HTTP simulada.

## Fora de escopo

- Alterar o protocolo de chamadas, trocar a lógica de prompts ou de map-reduce.
- Implementar descoberta automática de modelos ou fallback entre os modelos listados.
- Alterar outros perfis/providers ou instalar/configurar o servidor llama.cpp.

## Revisão de consistência

- O perfil usa `type: openai`, compatível com o ramo de chamada que já existe.
- A URL documentada inclui `/v1`; o código acrescenta `/chat/completions`.
- O default e a troca sob demanda são requisitos separados e estão ambos explícitos.
- O escopo limita mudanças a configuração, documentação e testes pertinentes.
