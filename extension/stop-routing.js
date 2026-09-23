// Mensagem interna: somente o background envia isto para o offscreen.
var MENSAGEM_PARAR_OFFSCREEN = "offscreen:stop";

if (typeof module !== "undefined") {
  module.exports = { MENSAGEM_PARAR_OFFSCREEN };
}
