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
      // Pass-through de TODOS os canais: preserva o áudio original
      // (stereo da aba) no monitoramento. O gain node do offscreen
      // controla o volume (aba: 1.0, mic: 0).
      for (let c = 0; c < input.length && c < output.length; c++) {
        output[c].set(input[c]);
      }
      // Converte Float32 → PCM16 (canal 0) e envia ao offscreen (que tem o WebSocket).
      const buf = input[0];
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
