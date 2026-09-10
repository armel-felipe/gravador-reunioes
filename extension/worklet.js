// worklet.js — processador de áudio (AudioWorklet) que converte Float32 → PCM16
// e envia os chunks para o offscreen document via port.postMessage().
// Roda em thread própria de áudio (sem glitches, API moderna).
class PCM16Processor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.channel = (options.processorOptions && options.processorOptions.channel) || "tab";
  }

  process(inputs, outputs) {
    const input = inputs[0];
    const output = outputs[0];
    if (input && input[0]) {
      const buf = input[0];
      // Pass-through: o áudio segue para o gain node do offscreen,
      // que controla o monitoramento (aba: volume 1.0, mic: volume 0).
      if (output && output[0]) {
        output[0].set(buf);
      }
      // Converte Float32 → PCM16 e envia ao offscreen (que tem o WebSocket).
      const pcm = new Int16Array(buf.length);
      for (let i = 0; i < buf.length; i++) {
        pcm[i] = Math.max(-1, Math.min(1, buf[i])) * 32767;
      }
      this.port.postMessage({ channel: this.channel, pcm: pcm.buffer }, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm16-processor", PCM16Processor);
