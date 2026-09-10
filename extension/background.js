// Service worker: gerencia o offscreen document e repassa mensagens do popup.

async function ensureOffscreen() {
  const has = await chrome.offscreen.hasDocument();
  if (has) {
    // Fecha o offscreen anterior: libera a aba de qualquer captura pendente
    // (o Chrome recusa nova captura enquanto houver uma ativa).
    await chrome.offscreen.closeDocument();
  }
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["USER_MEDIA"],
    justification: "Captura de áudio da aba e do microfone para gravação de reuniões."
  });
}

async function getStreamIdComRetry(tabId) {
  try {
    return await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
  } catch (e) {
    // 1 retry: o Chrome às vezes falha se outra captura estava sendo liberada
    await new Promise((r) => setTimeout(r, 500));
    return await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
  }
}

async function showToaster(tabId) {
  try {
    const { startTime } = await chrome.storage.session.get("startTime");
    await chrome.tabs.sendMessage(tabId, { type: "toaster:show", startTime: startTime || Date.now() });
  } catch (e) {
    // aba sem content script (ex.: chrome://) — o popup continua sendo o controle
  }
}

async function hideToaster(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: "toaster:hide" });
  } catch (e) {
    // ok
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
      if (!tab || tab.id === undefined) {
        sendResponse({ ok: false, error: "Nenhuma aba ativa encontrada." });
        return;
      }
      const streamId = await getStreamIdComRetry(tab.id);
      const resp = await chrome.runtime.sendMessage({ type: "start", nome: msg.nome, streamId, comMic: msg.comMic !== false });
      if (resp && resp.ok) {
        await chrome.storage.session.set({ recording: true });
        await showToaster(tab.id);
        sendResponse({ ok: true });
      } else {
        sendResponse({ ok: false, error: resp && resp.error });
      }
    })().catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }

  if (msg.type === "stop") {
    (async () => {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      await chrome.runtime.sendMessage({ type: "stop" });
      await chrome.storage.session.set({ recording: false });
      await chrome.storage.session.remove("startTime");
      if (tab && tab.id !== undefined) await hideToaster(tab.id);
      // Fecha o offscreen: libera a aba e o microfone imediatamente
      try {
        await chrome.offscreen.closeDocument();
      } catch (e) {
        // já fechado — ok
      }
      sendResponse({ ok: true });
    })();
    return true;
  }

  if (msg.type === "getState") {
    (async () => {
      const recording = await getRecordingState();
      const { startTime } = await chrome.storage.session.get("startTime");
      sendResponse({ recording, startTime: recording ? startTime : null });
    })();
    return true;
  }
});
