// Service worker: gerencia o offscreen document e repassa mensagens do popup.

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

async function getRecordingState() {
  const { recording } = await chrome.storage.session.get("recording");
  if (!recording) return false;
  const has = await chrome.offscreen.hasDocument();
  if (!has) {
    await chrome.storage.session.set({ recording: false });
    return false;
  }
  return true;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "start") {
    (async () => {
      await ensureOffscreen();
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
      const resp = await chrome.runtime.sendMessage({ type: "start", nome: msg.nome, streamId, comMic: msg.comMic !== false });
      if (resp && resp.ok) {
        await chrome.storage.session.set({ recording: true });
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
      await chrome.storage.session.set({ recording: false });
      sendResponse({ ok: true });
    })();
    return true;
  }

  if (msg.type === "getState") {
    getRecordingState().then((recording) => sendResponse({ recording }));
    return true;
  }
});
