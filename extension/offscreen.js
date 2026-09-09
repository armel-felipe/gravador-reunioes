// Offscreen document: única página da extensão com acesso a mediaDevices/AudioContext.
let ws = null;
let tabStream = null;
let micStream = null;
let processors = [];

function connectWs() {
  return new Promise((resolve, reject) => {
    const s = new WebSocket("ws://127.0.0.1:8765/ws");
    s.onopen = () => resolve(s);
    s.onerror = () => reject(new Error("ws error"));
    ws = s;
  });
}

function sendAudio(channel, stream) {
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  source.connect(processor);
  processor.connect(ctx.destination);
  processor.onaudioprocess = (e) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const buf = e.inputBuffer.getChannelData(0);
    const pcm = new Int16Array(buf.length);
    for (let i = 0; i < buf.length; i++) pcm[i] = Math.max(-1, Math.min(1, buf[i])) * 32767;
    const bytes = new Uint8Array(pcm.buffer);
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    ws.send(JSON.stringify({ type: "audio", channel, data: btoa(bin) }));
  };
  processors.push(processor);
}

async function startRecording(nome) {
  ws = await connectWs();
  ws.send(JSON.stringify({ type: "start", nome }));

  const tabId = (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id;
  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
  tabStream = await navigator.mediaDevices.getUserMedia({
    audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } }
  });
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });

  sendAudio("tab", tabStream);
  sendAudio("mic", micStream);
  return { ok: true };
}

function stopRecording() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "end" }));
    ws.close();
  }
  if (tabStream) tabStream.getTracks().forEach((t) => t.stop());
  if (micStream) micStream.getTracks().forEach((t) => t.stop());
  tabStream = null;
  micStream = null;
  processors = [];
  ws = null;
  return { ok: true };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "start") {
    startRecording(msg.nome).then(sendResponse).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }
  if (msg.type === "stop") {
    sendResponse(stopRecording());
  }
});
