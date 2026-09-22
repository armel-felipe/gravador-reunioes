// toaster-content.js — injeta o controle flutuante de gravação DENTRO da página
// (canto inferior direito, como um toast). Comunicado pelo background.
(() => {
  if (window.__gravadorToaster) return; // evita duplicação
  window.__gravadorToaster = true;

  const el = document.createElement("div");
  el.id = "gravador-toaster";
  el.style.cssText = `
    position: fixed; bottom: 16px; right: 16px; z-index: 2147483647;
    background: #1e1e1e; color: #fff; font-family: system-ui, sans-serif;
    padding: 10px 14px; border-radius: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    display: none; align-items: center; gap: 10px; font-size: 14px;
  `;
  el.innerHTML = `
    <span style="width:10px;height:10px;border-radius:50%;background:#ff3b30;display:inline-block;animation:gravadorPulse 1.2s infinite;"></span>
    <span id="gravador-timer" style="font-weight:bold;font-variant-numeric:tabular-nums;">00:00</span>
    <button id="gravador-stop" style="background:#ff3b30;color:#fff;border:none;padding:5px 12px;border-radius:6px;cursor:pointer;font-size:13px;">Parar</button>
    <style>@keyframes gravadorPulse{0%,100%{opacity:1}50%{opacity:.3}}</style>
  `;
  document.documentElement.appendChild(el);

  const timerEl = el.querySelector("#gravador-timer");
  const stopBtn = el.querySelector("#gravador-stop");

  // Se a extensão for recarregada/atualizada, o contexto é invalidado e o
  // content script antigo fica órfão na página. Detecta e se auto-destrói.
  function contextoInvalido(e) {
    return e && e.message && e.message.includes("Extension context invalidated");
  }

  function limparOrfao() {
    clearInterval(timerInterval);
    if (el && el.parentNode) el.parentNode.removeChild(el);
    window.__gravadorToaster = false;
  }

  stopBtn.addEventListener("click", () => {
    try {
      chrome.runtime.sendMessage({ type: "stop" });
    } catch (e) {
      if (contextoInvalido(e)) limparOrfao();
    }
  });

  // Content scripts NÃO têm acesso a chrome.storage.session (só popup/background).
  // O estado vem do background via mensagens.
  let startTime = null;

  function updateTimer() {
    if (!startTime) return;
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const s = String(elapsed % 60).padStart(2, "0");
    timerEl.textContent = `${m}:${s}`;
  }

  try {
    chrome.runtime.onMessage.addListener((msg) => {
      if (msg.type === "toaster:show") {
        startTime = msg.startTime || Date.now();
        el.style.display = "flex";
        updateTimer();
      } else if (msg.type === "toaster:hide") {
        el.style.display = "none";
        startTime = null;
      }
    });
  } catch (e) {
    if (contextoInvalido(e)) limparOrfao();
  }

  // Estado inicial (ex.: página recarregou durante a gravação)
  try {
    chrome.runtime.sendMessage({ type: "getState" }, (resp) => {
      if (resp && resp.recording && resp.isRecordingTab) {
        startTime = resp.startTime || Date.now();
        el.style.display = "flex";
        updateTimer();
      } else {
        startTime = null;
        el.style.display = "none";
      }
    });
  } catch (e) {
    if (contextoInvalido(e)) limparOrfao();
  }

  const timerInterval = setInterval(updateTimer, 1000);
})();
