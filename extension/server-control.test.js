const test = require("node:test");
const assert = require("node:assert/strict");

const { nextServerState, aguardarServidorOnline } = require("./server-control.js");

test("mapeia resposta online para o estado Online", () => {
  assert.deepEqual(nextServerState({ ok: true, online: true }), { state: "online", message: "Servidor online" });
});

test("mapeia resposta offline para o estado Offline", () => {
  assert.deepEqual(nextServerState({ ok: true, online: false }), { state: "offline", message: "Servidor offline" });
});

test("aguarda até o health responder online", async () => {
  const respostas = [
    { ok: true, online: false },
    { ok: true, online: true },
  ];
  const resultado = await aguardarServidorOnline(
    async () => respostas.shift(),
    { attempts: 3, sleep: async () => {} },
  );

  assert.deepEqual(resultado, { ok: true, online: true });
});

test("falha com timeout quando o servidor não fica online", async () => {
  await assert.rejects(
    aguardarServidorOnline(async () => ({ ok: true, online: false }), { attempts: 2, sleep: async () => {} }),
    /não respondeu/,
  );
});
