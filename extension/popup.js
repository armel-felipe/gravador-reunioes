const nomeInput = document.getElementById("nome");
const toggleBtn = document.getElementById("toggle");
const statusDiv = document.getElementById("status");
const timerDiv = document.getElementById("timer");
const comMicCheckbox = document.getElementById("comMic");

let recording = false;
let timerInterval = null;
let seconds = 0;

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

function tick() {
  seconds++;
  const m = String(Math.floor(seconds / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  timerDiv.textContent = `${m}:${s}`;
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
    const resp = await chrome.runtime.sendMessage({ type: "start", nome, comMic: comMicCheckbox.checked });
    if (resp && resp.ok) {
      recording = true;
      seconds = 0;
      timerInterval = setInterval(tick, 1000);
      statusDiv.textContent = "Gravando…";
    } else {
      statusDiv.textContent = "Erro ao iniciar gravação.";
    }
  } else {
    await chrome.runtime.sendMessage({ type: "stop" });
    recording = false;
    clearInterval(timerInterval);
    statusDiv.textContent = "Gravação salva. Processe no chat do OpenWork.";
  }
  updateUI();
});

// Restaura estado se o popup foi fechado e reaberto
chrome.runtime.sendMessage({ type: "getState" }, (resp) => {
  if (resp && resp.recording) {
    recording = true;
    updateUI();
    statusDiv.textContent = "Gravando…";
  }
});
