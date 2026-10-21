const nomeInput = document.getElementById("nome");
const toggleBtn = document.getElementById("toggle");
const statusDiv = document.getElementById("status");
const timerDiv = document.getElementById("timer");
const comMicCheckbox = document.getElementById("comMic");
const permMicBtn = document.getElementById("permMic");
const serverStatusDiv = document.getElementById("serverStatus");
const serverToggleBtn = document.getElementById("serverToggle");
const serverConfirm = document.getElementById("serverConfirm");
const confirmServerStopBtn = document.getElementById("confirmServerStop");

// Abre a página de permissão de microfone (aba dedicada — o prompt não é
// dispensado, diferente do popup que fecha ao perder o foco).
permMicBtn.addEventListener("click", () => {
  chrome.tabs.create({ url: chrome.runtime.getURL("mic.html") });
});

let recording = false;
let timerInterval = null;
let servidorOnline = false;
let operacaoServidor = false;

function enviarComandoServidor(type) {
  return new Promise((resolve) => chrome.runtime.sendMessage({ type }, resolve));
}

function atualizarEstadoServidor(state, message) {
  servidorOnline = state === "online";
  serverStatusDiv.textContent = `Servidor: ${message.toLowerCase()}`;
  serverToggleBtn.disabled = operacaoServidor;
  if (state === "online") serverToggleBtn.textContent = "Desligar servidor";
  else if (state === "offline") serverToggleBtn.textContent = "Ligar servidor";
  else serverToggleBtn.textContent = message;
  updateUI();
}

async function atualizarStatusServidor() {
  const response = await enviarComandoServidor("server:status");
  const state = nextServerState(response);
  atualizarEstadoServidor(state.state, state.message);
  return response;
}

async function ligarServidor() {
  operacaoServidor = true;
  atualizarEstadoServidor("starting", "Ligando servidor…");
  const startResponse = await enviarComandoServidor("server:start");
  if (!startResponse || !startResponse.ok) {
    operacaoServidor = false;
    atualizarEstadoServidor("error", (startResponse && startResponse.error) || "Falha ao ligar servidor");
    return;
  }
  try {
    await aguardarServidorOnline(() => enviarComandoServidor("server:status"));
    operacaoServidor = false;
    atualizarEstadoServidor("online", "Servidor online");
    statusDiv.textContent = "Servidor ligado.";
  } catch (e) {
    operacaoServidor = false;
    atualizarEstadoServidor("error", e.message);
  }
}

async function desligarServidor() {
  operacaoServidor = true;
  atualizarEstadoServidor("stopping", "Desligando servidor…");
  const response = await enviarComandoServidor("server:stop");
  operacaoServidor = false;
  if (!response || !response.ok) {
    atualizarEstadoServidor("error", (response && response.error) || "Falha ao desligar servidor");
    return;
  }
  recording = false;
  clearInterval(timerInterval);
  timerInterval = null;
  atualizarEstadoServidor("offline", "Servidor offline");
  statusDiv.textContent = "Servidor desligado.";
}

function formatTime(totalSeconds) {
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const s = String(totalSeconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function updateTimer() {
  chrome.storage.session.get("startTime", ({ startTime }) => {
    if (!startTime) return;
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    timerDiv.textContent = formatTime(elapsed);
  });
}

async function serverOnline() {
  try {
    const r = await fetch("http://127.0.0.1:8765/health");
    return r.ok;
  } catch {
    return false;
  }
}

function updateUI() {
  toggleBtn.textContent = recording ? "Parar" : "Gravar";
  timerDiv.hidden = !recording;
  nomeInput.disabled = recording;
  comMicCheckbox.disabled = recording;
  toggleBtn.disabled = !recording && (!servidorOnline || operacaoServidor);
}

serverToggleBtn.addEventListener("click", () => {
  if (servidorOnline) {
    serverConfirm.showModal();
  } else {
    ligarServidor();
  }
});

confirmServerStopBtn.addEventListener("click", (event) => {
  event.preventDefault();
  serverConfirm.close();
  desligarServidor();
});

toggleBtn.addEventListener("click", async () => {
  if (!recording) {
    const nome = nomeInput.value.trim();
    if (!nome) {
      statusDiv.textContent = "Digite o nome da reunião.";
      return;
    }
    if (!servidorOnline) {
      await atualizarStatusServidor();
    }
    if (!servidorOnline) {
      statusDiv.textContent = "Servidor offline — clique em Ligar servidor.";
      return;
    }
    // Pedir a permissão do microfone AQUI (popup visível) — o prompt aparece
    // corretamente. No offscreen (página oculta) o prompt é dispensado
    // silenciosamente (NotAllowedError: Permission dismissed).
    if (comMicCheckbox.checked) {
      let estado = "prompt";
      try {
        const status = await navigator.permissions.query({ name: "microphone" });
        estado = status.state;
      } catch (e) {
        // API não suportada — segue o fluxo normal
      }
      if (estado === "denied") {
        statusDiv.textContent = "Microfone bloqueado. Clique no 🔒 da barra de endereço → Microfone → Permitir.";
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop()); // só para conceder a permissão
      } catch (e) {
        statusDiv.textContent = "Permissão de microfone negada. Clique no 🔒 da barra de endereço → Microfone → Permitir.";
        return;
      }
    }
    const resp = await chrome.runtime.sendMessage({ type: "start", nome, comMic: comMicCheckbox.checked });
    if (resp && resp.ok) {
      recording = true;
      updateTimer();
      timerInterval = setInterval(updateTimer, 1000);
      statusDiv.textContent = "Gravando…";
    } else {
      statusDiv.textContent = "Erro: " + ((resp && resp.error) || "desconhecido");
    }
  } else {
    await chrome.runtime.sendMessage({ type: "stop" });
    recording = false;
    clearInterval(timerInterval);
    await chrome.storage.session.remove("startTime");
    statusDiv.textContent = "Gravação salva. Processe no chat do OpenWork.";
  }
  updateUI();
});

// Restaura estado se o popup foi fechado e reaberto
chrome.runtime.sendMessage({ type: "getState" }, (resp) => {
  if (resp && resp.recording) {
    recording = true;
    updateUI();
    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
    statusDiv.textContent = "Gravando…";
  }
});

atualizarStatusServidor().catch((e) => {
  atualizarEstadoServidor("error", e.message);
});
