function nextServerState(response) {
  if (response && response.ok && response.online) {
    return { state: "online", message: "Servidor online" };
  }
  if (response && response.ok && !response.online) {
    return { state: "offline", message: "Servidor offline" };
  }
  return { state: "error", message: (response && response.error) || "Não foi possível consultar o servidor." };
}

async function aguardarServidorOnline(requestStatus, { attempts = 12, sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)), delayMs = 500 } = {}) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const response = await requestStatus();
    if (!response || response.ok === false) {
      throw new Error((response && response.error) || "Não foi possível consultar o servidor.");
    }
    if (response.online) return response;
    if (attempt + 1 < attempts) await sleep(delayMs);
  }
  throw new Error("servidor não respondeu dentro do tempo esperado");
}

globalThis.nextServerState = nextServerState;
globalThis.aguardarServidorOnline = aguardarServidorOnline;
if (typeof module !== "undefined") module.exports = { nextServerState, aguardarServidorOnline };
