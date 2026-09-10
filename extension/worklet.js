// worklet.js — processador de áudio (AudioWorklet) que converte Float32 → PCM16
// e envia os chunks para o offscreen document via port.postMessage().
// Roda em thread própria de áudio (sem glitches, API moderna).
class PCM16Processor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.channel = (options.processorOptions && options.processorOptions.channel) || "tab";
    // O AudioWorklet processa em blocos de 128 frames (~2.7ms a 48kHz).
    // Acumula até 4096 samples antes de enviar (mesmo tamanho do ScriptProcessor
    // antigo) — evita milhares de mensagens WebSocket por minuto.
    this.buffer = new Int16Array(4096);
    this.bufferLen = 0;
  }

  process(inputs, outputs) {
    const input = inputs[0];
    const output = outputs[0];
    if (input && input[0]) {
      // Pass-through de TODOS os canais: preserva o áudio original
      // (stereo da aba) no monitoramento. O gain node do offscreen
      // controla o volume (aba: 1.0, mic: 0).
      for (let c = 0; c < input.length && c < output.length; c++) {
        output[c].set(input[c]);
      }
      // Converte Float32 → PCM16 e acumula
      const buf = input[0];
      for (let i = 0; i < buf.length; i++) {
        this.buffer[this.bufferLen++] = Math.max(-1, Math.min(1, buf[i])) * 32767;
        if (this.bufferLen >= 4096) {
          this.port.postMessage(
            { channel: this.channel, pcm: this.buffer.buffer },
            [this.buffer.buffer]
          );
          this.buffer = new Int16Array(4096);
          this.bufferLen = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm16-processor", PCM16Processor);
