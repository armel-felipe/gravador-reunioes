// Service worker: gerencia o offscreen document e repassa mensagens do popup.
importScripts("stop-routing.js");

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
    const msg = { type: "toaster:show", startTime: startTime || Date.now() };
    try {
      await chrome.tabs.sendMessage(tabId, msg);
    } catch (e) {
      // Página aberta antes da recarga da extensão não tem o content script.
      // Injeta na hora e tenta de novo.
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["toaster-lifecycle.js", "toaster-content.js"]
      });
      await chrome.tabs.sendMessage(tabId, msg);
    }
  } catch (e) {
    // aba sem suporte (ex.: chrome://) — o popup continua sendo o controle
  }
}

async function hideToaster(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: "toaster:hide" });
  } catch (e) {
    // ok
  }
}

async function hideToastersEmTodasAsAbas() {
  const tabs = await chrome.tabs.query({});
  await Promise.allSettled(tabs.map((tab) => hideToaster(tab.id)));
}

async function restaurarToasterSeGravando() {
  const { recording, recordingTabId } = await chrome.storage.session.get(["recording", "recordingTabId"]);
  if (recording && recordingTabId !== undefined) {
    await showToaster(recordingTabId);
  }
}

async function pararOffscreen() {
  if (!(await chrome.offscreen.hasDocument())) return { ok: true };
  try {
    return await chrome.runtime.sendMessage({ type: MENSAGEM_PARAR_OFFSCREEN });
  } catch (e) {
    return { ok: false, error: "Não foi possível encerrar a gravação." };
  }
}

async function sendNativeServerCommand(action) {
  try {
    return await chrome.runtime.sendNativeMessage("com.armel.gravador.server", { action });
  } catch (e) {
    return { ok: false, error: "Ponte do servidor não instalada ou indisponível." };
  }
}

async function encerrarGravacao({ forceCleanup = false } = {}) {
  const recording = await getRecordingState();
  if (!recording && !forceCleanup) return { ok: true, recording: false };

  const [offscreenResponse] = await Promise.all([
    pararOffscreen(),
    hideToastersEmTodasAsAbas(),
  ]);
  if (offscreenResponse && offscreenResponse.ok === false) {
    return offscreenResponse;
  }

  await chrome.storage.session.set({ recording: false });
  await chrome.storage.session.remove("startTime", "recordingTabId");
  try {
    await chrome.offscreen.closeDocument();
  } catch (e) {
    // já fechado — ok
  }
  return { ok: true, recording: true };
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

chrome.runtime.onInstalled.addListener(() => {
  restaurarToasterSeGravando().catch(() => {});
});

chrome.runtime.onStartup.addListener(() => {
  restaurarToasterSeGravando().catch(() => {});
});

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
        await chrome.storage.session.set({ recording: true, recordingTabId: tab.id, startTime: Date.now() });
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
      sendResponse(await encerrarGravacao({ forceCleanup: true }));
    })().catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }

  if (msg.type === "server:status" || msg.type === "server:start") {
    sendNativeServerCommand(msg.type === "server:status" ? "status" : "start")
      .then(sendResponse);
    return true;
  }

  if (msg.type === "server:stop") {
    (async () => {
      const recordingResponse = await encerrarGravacao();
      if (!recordingResponse.ok) {
        sendResponse(recordingResponse);
        return;
      }
      sendResponse(await sendNativeServerCommand("stop"));
    })().catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }

  if (msg.type === "getState") {
    (async () => {
      const recording = await getRecordingState();
      const { startTime, recordingTabId } = await chrome.storage.session.get(["startTime", "recordingTabId"]);
      const isRecordingTab = recording && sender && sender.tab && sender.tab.id === recordingTabId;
      sendResponse({ recording, startTime: recording ? startTime : null, isRecordingTab });
    })();
    return true;
  }
});
