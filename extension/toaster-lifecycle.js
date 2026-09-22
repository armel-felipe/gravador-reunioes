function prepararToaster(documento, janela) {
  const anterior = documento.getElementById("gravador-toaster");
  if (anterior && typeof anterior.remove === "function") anterior.remove();
  janela.__gravadorToaster = true;
}

if (typeof module !== "undefined") module.exports = { prepararToaster };
