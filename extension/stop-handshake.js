// Encerra a gravação somente depois que o servidor confirmou que o WAV foi salvo.
function aguardarEncerramento(ws, { timeoutMs = 5000 } = {}) {
  return new Promise((resolve, reject) => {
    const mensagemAnterior = ws.onmessage;
    let timer;
    let concluido = false;

    function limpar() {
      clearTimeout(timer);
      if (ws.onmessage === receberMensagem) ws.onmessage = mensagemAnterior || null;
      if (ws.onerror === receberErro) ws.onerror = null;
      if (ws.onclose === receberFechamento) ws.onclose = null;
    }

    function finalizar(fn, valor) {
      if (concluido) return;
      concluido = true;
      limpar();
      fn(valor);
    }

    function receberMensagem(evento) {
      let mensagem;
      try {
        mensagem = JSON.parse(evento.data);
      } catch (erro) {
        finalizar(reject, erro);
        return;
      }
      if (mensagem.type === "ended") {
        finalizar(resolve, mensagem);
      } else if (mensagem.type === "error") {
        finalizar(reject, new Error(mensagem.message || "erro ao encerrar gravação"));
      } else if (mensagemAnterior) {
        mensagemAnterior(evento);
      }
    }

    function receberErro() {
      finalizar(reject, new Error("erro no WebSocket ao encerrar gravação"));
    }

    function receberFechamento() {
      finalizar(reject, new Error("WebSocket fechado antes da confirmação ended"));
    }

    ws.onmessage = receberMensagem;
    ws.onerror = receberErro;
    ws.onclose = receberFechamento;
    timer = setTimeout(() => {
      finalizar(reject, new Error("timeout aguardando confirmação ended"));
    }, timeoutMs);

    try {
      ws.send(JSON.stringify({ type: "end" }));
    } catch (erro) {
      finalizar(reject, erro);
    }
  });
}

globalThis.aguardarEncerramento = aguardarEncerramento;
if (typeof module !== "undefined") module.exports = { aguardarEncerramento };
