// Offscreen document: única página da extensão com acesso a mediaDevices/AudioContext.
// A captura usa AudioWorkletNode (API moderna) — o processamento roda em thread própria.
let ws = null;
let tabStream = null;
let micStream = null;
let workletNodes = [];
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

function sendPcmToServer(channel, pcmBuffer) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const bytes = new Uint8Array(pcmBuffer);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  ws.send(JSON.stringify({ type: "audio", channel, data: btoa(bin) }));
}

async function sendAudio(channel, stream, volume) {
  const source = ctx.createMediaStreamSource(stream);
  const gain = ctx.createGain();
  // tab: volume 1.0 (usuário continua ouvindo a reunião — o tabCapture silencia a aba)
  // mic: volume 0 (evita feedback do microfone com os alto-falantes)
  gain.gain.value = volume;

  const node = new AudioWorkletNode(ctx, "pcm16-processor", {
    processorOptions: { channel }
  });
  node.port.onmessage = (e) => sendPcmToServer(e.data.channel, e.data.pcm);

  source.connect(node);
  node.connect(gain);
  gain.connect(ctx.destination);
  workletNodes.push(node);
}

async function startRecording(nome, streamId, comMic) {
  try {
    // 1. Consome o streamId IMEDIATAMENTE — ele expira em ~5s.
    //    Se demorar (connectWs, addModule), o Chrome rejeita a captura.
    tabStream = await navigator.mediaDevices.getUserMedia({
      audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } }
    });

    // 2. Conecta ao servidor e prepara o áudio
    ws = await connectWs();
    ctx = new AudioContext();
    // addModule exige URL absoluta em offscreen documents (caminho relativo falha)
    await ctx.audioWorklet.addModule(chrome.runtime.getURL("worklet.js"));
    ws.send(JSON.stringify({ type: "start", nome, sample_rate: ctx.sampleRate }));

    // 3. Espera a confirmação do servidor antes de prosseguir.
    //    Se o servidor rejeitar (nome inválido, etc.), aborta com o erro.
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("timeout aguardando servidor")), 5000);
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "started") {
          clearTimeout(timeout);
          resolve(msg);
        } else if (msg.type === "error") {
          clearTimeout(timeout);
          reject(new Error(msg.message));
        }
      };
    });

    // 4. Inicia o monitoramento e a captura
    await sendAudio("tab", tabStream, 1.0);

    if (comMic) {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      await sendAudio("mic", micStream, 0);
    }
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

async function stopRecording() {
  const currentWs = ws;
  if (currentWs && currentWs.readyState === WebSocket.OPEN) {
    try {
      await aguardarEncerramento(currentWs);
    } catch (e) {
      // O servidor ainda salva o que recebeu quando a conexão cai.
    } finally {
      currentWs.close();
    }
  }
  if (tabStream) tabStream.getTracks().forEach((t) => t.stop());
  if (micStream) micStream.getTracks().forEach((t) => t.stop());
  tabStream = null;
  micStream = null;
  workletNodes = [];
  ws = null;
  if (ctx) {
    ctx.close();
    ctx = null;
  }
  return { ok: true };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "start") {
    startRecording(msg.nome, msg.streamId, msg.comMic !== false).then(sendResponse).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }
  if (msg.type === "stop") {
    stopRecording().then(sendResponse).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }
});
