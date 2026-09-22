const test = require("node:test");
const assert = require("node:assert/strict");

const { aguardarEncerramento } = require("./stop-handshake.js");

test("aguarda a confirmação ended antes de concluir a parada", async () => {
  const ws = {
    readyState: 1,
    mensagens: [],
    fechado: false,
    send(mensagem) {
      this.mensagens.push(JSON.parse(mensagem));
      queueMicrotask(() => this.onmessage({ data: JSON.stringify({ type: "ended", wav: "reuniao.wav" }) }));
    },
    close() {
      this.fechado = true;
    },
  };

  const resposta = await aguardarEncerramento(ws, { timeoutMs: 100 });

  assert.deepEqual(resposta, { type: "ended", wav: "reuniao.wav" });
  assert.deepEqual(ws.mensagens, [{ type: "end" }]);
  assert.equal(ws.fechado, false, "o helper não deve fechar a conexão sozinho");
});
