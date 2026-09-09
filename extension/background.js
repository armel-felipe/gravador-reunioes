// Service worker: gerencia o offscreen document e repassa mensagens do popup.
let recording = false;

async function ensureOffscreen() {
  const has = await chrome.offscreen.hasDocument();
  if (!has) {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["USER_MEDIA"],
      justification: "Captura de áudio da aba e do microfone para gravação de reuniões."
    });
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "start") {
    (async () => {
      await ensureOffscreen();
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
      const resp = await chrome.runtime.sendMessage({ type: "start", nome: msg.nome, streamId });
      if (resp && resp.ok) {
        recording = true;
        sendResponse({ ok: true });
      } else {
        sendResponse({ ok: false, error: resp && resp.error });
      }
    })().catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }

  if (msg.type === "stop") {
    (async () => {
      await chrome.runtime.sendMessage({ type: "stop" });
      recording = false;
      sendResponse({ ok: true });
    })();
    return true;
  }

  if (msg.type === "getState") {
    sendResponse({ recording });
  }
});
