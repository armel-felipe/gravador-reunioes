const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function carregarBackground({ recording = false } = {}) {
  const eventos = [];
  let listener;
  const estado = { recording, recordingTabId: 123 };
  const chrome = {
    offscreen: {
      async hasDocument() { return recording; },
      async closeDocument() {},
    },
    runtime: {
      onInstalled: { addListener() {} },
      onStartup: { addListener() {} },
      onMessage: { addListener(fn) { listener = fn; } },
      async sendMessage(message) {
        eventos.push(`offscreen:${message.type}`);
        return { ok: true };
      },
      async sendNativeMessage(host, message) {
        eventos.push(`native:${message.action}`);
        return { ok: true, action: message.action, online: message.action !== "stop" };
      },
    },
    storage: {
      session: {
        async get(keys) {
          if (Array.isArray(keys)) return Object.fromEntries(keys.map((key) => [key, estado[key]]));
          return { [keys]: estado[keys] };
        },
        async set(values) { Object.assign(estado, values); },
        async remove(...keys) { keys.flat().forEach((key) => delete estado[key]); },
      },
    },
    tabs: {
      async query() { return [{ id: 123 }]; },
      async sendMessage() {},
    },
  };
  const context = vm.createContext({
    chrome,
    importScripts() {},
    MENSAGEM_PARAR_OFFSCREEN: "offscreen:stop",
    setTimeout,
    clearTimeout,
    Promise,
  });
  vm.runInContext(fs.readFileSync(require.resolve("./background.js"), "utf8"), context, { filename: "background.js" });
  return { eventos, listener };
}

test("consulta o estado do servidor pelo host Native Messaging", async () => {
  const { eventos, listener } = carregarBackground();
  const resposta = await new Promise((resolve) => listener({ type: "server:status" }, {}, resolve));

  assert.deepEqual(JSON.parse(JSON.stringify(resposta)), { ok: true, action: "status", online: true });
  assert.deepEqual(eventos, ["native:status"]);
});

test("solicita a inicialização do servidor pelo host Native Messaging", async () => {
  const { eventos, listener } = carregarBackground();
  const resposta = await new Promise((resolve) => listener({ type: "server:start" }, {}, resolve));

  assert.deepEqual(JSON.parse(JSON.stringify(resposta)), { ok: true, action: "start", online: true });
  assert.deepEqual(eventos, ["native:start"]);
});

test("para a gravação antes de pedir o desligamento do servidor", async () => {
  const { eventos, listener } = carregarBackground({ recording: true });
  const resposta = await new Promise((resolve) => listener({ type: "server:stop" }, {}, resolve));

  assert.equal(resposta.ok, true);
  assert.deepEqual(eventos.slice(-2), ["offscreen:offscreen:stop", "native:stop"]);
});
