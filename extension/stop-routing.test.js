const test = require("node:test");
const assert = require("node:assert/strict");

const { MENSAGEM_PARAR_OFFSCREEN } = require("./stop-routing.js");

test("usa uma mensagem interna distinta para parar o offscreen", () => {
  assert.equal(MENSAGEM_PARAR_OFFSCREEN, "offscreen:stop");
  assert.notEqual(MENSAGEM_PARAR_OFFSCREEN, "stop");
});
