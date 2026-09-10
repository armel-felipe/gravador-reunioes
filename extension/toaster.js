// Toaster: janelinha flutuante de controle durante a gravação.
// Mostra timer + botão Parar, e fica visível mesmo com o popup fechado.
const timerDiv = document.getElementById("timer");
const stopBtn = document.getElementById("stop");

function updateTimer() {
  chrome.storage.session.get("startTime", ({ startTime }) => {
    if (!startTime) return;
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const s = String(elapsed % 60).padStart(2, "0");
    timerDiv.textContent = `${m}:${s}`;
  });
}

stopBtn.addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "stop" });
  window.close();
});

updateTimer();
setInterval(updateTimer, 1000);
