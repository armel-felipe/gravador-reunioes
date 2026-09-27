const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

test("inicia uma nova gravação com startTime novo antes de mostrar o toaster", async () => {
  const estado = { startTime: 1000 };
  const alteracoes = [];
  const mensagens = [];
  let listener;

  const chrome = {
    offscreen: {
      async hasDocument() { return true; },
      async closeDocument() {},
      async createDocument() {},
    },
    tabCapture: {
      async getMediaStreamId() { return "stream-id"; },
    },
    runtime: {
      onInstalled: { addListener() {} },
      onStartup: { addListener() {} },
      onMessage: { addListener(fn) { listener = fn; } },
      async sendMessage() { return { ok: true }; },
    },
    storage: {
      session: {
        async get(chaves) {
          if (Array.isArray(chaves)) {
            return Object.fromEntries(chaves.map((chave) => [chave, estado[chave]]));
          }
          return { [chaves]: estado[chaves] };
        },
        async set(valores) {
          Object.assign(estado, valores);
          alteracoes.push(valores);
        },
      },
    },
    tabs: {
      async query() { return [{ id: 123 }]; },
      async sendMessage(tabId, mensagem) {
        mensagens.push({ tabId, mensagem });
      },
    },
  };

  const contexto = vm.createContext({
    chrome,
    importScripts() {},
    Date: { now: () => 5000 },
    Promise,
    setTimeout,
    clearTimeout,
  });
  const codigo = fs.readFileSync(require.resolve("./background.js"), "utf8");
  vm.runInContext(codigo, contexto, { filename: "background.js" });

  await new Promise((resolve) => {
    listener({ type: "start", nome: "nova", comMic: false }, {}, (resposta) => {
      assert.deepEqual(JSON.parse(JSON.stringify(resposta)), { ok: true });
      resolve();
    });
  });

  assert.equal(estado.startTime, 5000);
  assert.deepEqual(JSON.parse(JSON.stringify(mensagens)), [
    { tabId: 123, mensagem: { type: "toaster:show", startTime: 5000 } },
  ]);
  assert.equal(alteracoes.some((valores) => valores.startTime === 5000), true);
});
