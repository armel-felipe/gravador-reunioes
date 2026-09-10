const nomeInput = document.getElementById("nome");
const toggleBtn = document.getElementById("toggle");
const statusDiv = document.getElementById("status");
const timerDiv = document.getElementById("timer");
const comMicCheckbox = document.getElementById("comMic");

let recording = false;
let timerInterval = null;

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
}

toggleBtn.addEventListener("click", async () => {
  if (!recording) {
    const nome = nomeInput.value.trim();
    if (!nome) {
      statusDiv.textContent = "Digite o nome da reunião.";
      return;
    }
    if (!(await serverOnline())) {
      statusDiv.textContent = "Servidor offline — rode ./start.sh";
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
      await chrome.storage.session.set({ startTime: Date.now() });
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
