// mic.js — pede a permissão de microfone numa aba dedicada (não fecha ao perder foco).
const btn = document.getElementById("pedir");
const status = document.getElementById("status");

btn.addEventListener("click", async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((t) => t.stop());
    status.textContent = "✅ Permissão concedida! Pode fechar esta aba e gravar.";
    status.style.color = "#4caf50";
  } catch (e) {
    status.textContent = "❌ Negada. Clique no 🔒 da barra de endereço → Microfone → Permitir e tente de novo.";
    status.style.color = "#ff3b30";
  }
});
