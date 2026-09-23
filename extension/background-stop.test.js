const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function carregarBackground({ respostaOffscreen = new Promise(() => {}) } = {}) {
  const mensagensToaster = [];
  let listener;

  const chrome = {
    offscreen: {
      async hasDocument() { return true; },
      async closeDocument() {},
    },
    runtime: {
      onInstalled: { addListener() {} },
      onStartup: { addListener() {} },
      onMessage: { addListener(fn) { listener = fn; } },
      sendMessage: async () => respostaOffscreen,
    },
    storage: {
      session: {
        async get(keys) {
          if (keys === "recordingTabId") return { recordingTabId: 123 };
          return {};
        },
        async set() {},
        async remove() {},
      },
    },
    tabs: {
      async query() { return [{ id: 123 }]; },
      async sendMessage(tabId, mensagem) {
        mensagensToaster.push({ tabId, mensagem });
      },
    },
  };

  const contexto = vm.createContext({
    chrome,
    importScripts() {},
    MENSAGEM_PARAR_OFFSCREEN: "offscreen:stop",
    setTimeout,
    clearTimeout,
    Promise,
  });
  const codigo = fs.readFileSync(require.resolve("./background.js"), "utf8");
  vm.runInContext(codigo, contexto, { filename: "background.js" });

  return { listener, mensagensToaster };
}

test("esconde o toaster imediatamente enquanto a parada do offscreen finaliza", async () => {
  const { listener, mensagensToaster } = carregarBackground();
  const respostas = [];

  listener({ type: "stop" }, {}, (resposta) => respostas.push(resposta));
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.deepEqual(JSON.parse(JSON.stringify(mensagensToaster)), [
    { tabId: 123, mensagem: { type: "toaster:hide" } },
  ]);
  assert.deepEqual(respostas, []);
});
