// Offscreen document: única página da extensão com acesso a mediaDevices/AudioContext.
let ws = null;
let tabStream = null;
let micStream = null;
let processors = [];
let ctx = null;

function connectWs() {
  return new Promise((resolve, reject) => {
    const s = new WebSocket("ws://127.0.0.1:8765/ws");
    s.onopen = () => resolve(s);
    s.onerror = () => reject(new Error("ws error"));
    s.onclose = () => reject(new Error("ws closed"));
    ws = s;
  });
}

function sendAudio(channel, stream) {
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  const gain = ctx.createGain();
  gain.gain.value = 0;
  source.connect(processor);
  processor.connect(gain);
  gain.connect(ctx.destination);
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

async function startRecording(nome, streamId) {
  try {
    ws = await connectWs();
    ctx = new AudioContext();
    ws.send(JSON.stringify({ type: "start", nome, sample_rate: ctx.sampleRate }));

    tabStream = await navigator.mediaDevices.getUserMedia({
      audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } }
    });
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    sendAudio("tab", tabStream);
    sendAudio("mic", micStream);
    return { ok: true };
  } catch (e) {
    if (tabStream) tabStream.getTracks().forEach((t) => t.stop());
    if (micStream) micStream.getTracks().forEach((t) => t.stop());
    tabStream = null;
    micStream = null;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "end" }));
      ws.close();
    }
    ws = null;
    throw e;
  }
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
  if (ctx) {
    ctx.close();
    ctx = null;
  }
  return { ok: true };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "start") {
    startRecording(msg.nome, msg.streamId).then(sendResponse).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }
  if (msg.type === "stop") {
    sendResponse(stopRecording());
  }
});
