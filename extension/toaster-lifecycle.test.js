const test = require("node:test");
const assert = require("node:assert/strict");

const { prepararToaster } = require("./toaster-lifecycle.js");

test("substitui um toaster órfão quando a extensão é reinjetada", () => {
  const antigo = { removido: false, remove() { this.removido = true; } };
  const documento = {
    getElementById(id) {
      return id === "gravador-toaster" ? antigo : null;
    },
  };
  const janela = { __gravadorToaster: true };

  prepararToaster(documento, janela);

  assert.equal(antigo.removido, true);
  assert.equal(janela.__gravadorToaster, true);
});
