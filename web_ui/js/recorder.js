const MIME_CANDIDATES = [
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
  "audio/webm;codecs=opus",
  "audio/webm",
];

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return "";
  return MIME_CANDIDATES.find((mime) => MediaRecorder.isTypeSupported(mime)) || "";
}

function extensionForMime(mimeType) {
  if (!mimeType) return "bin";
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("webm")) return "webm";
  return "bin";
}

export class VoiceRecorder {
  constructor({ minDurationSeconds = 3, onStateChange, onReady, onTooShort, onError, onVoiceLevel }) {
    this.minDurationSeconds = minDurationSeconds;
    this.onStateChange = onStateChange;
    this.onReady = onReady;
    this.onTooShort = onTooShort;
    this.onError = onError;
    this.onVoiceLevel = onVoiceLevel;

    this.recorder = null;
    this.stream = null;
    this.chunks = [];
    this.startedAt = 0;
    this.lastRecording = null;
    this.lastDuration = 0;
    this.mimeType = "";
    this.audioContext = null;
    this.analyser = null;
    this.voiceData = null;
    this.voiceRaf = null;
    this.voiceThreshold = 0.02;
    this.lastVoiceEmitTs = 0;
  }

  get isRecording() {
    return Boolean(this.recorder && this.recorder.state === "recording");
  }

  getLastRecording() {
    return this.lastRecording;
  }

  async toggle() {
    if (this.isRecording) {
      await this.stop();
      return;
    }
    await this.start();
  }

  async start() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      this.onError?.("Браузер не поддерживает запись голоса.");
      return;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.chunks = [];
      this.mimeType = pickMimeType();

      const recorder = this.mimeType
        ? new MediaRecorder(this.stream, { mimeType: this.mimeType })
        : new MediaRecorder(this.stream);

      this.recorder = recorder;
      this.startedAt = Date.now();
      this._startVoiceMonitor();

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          this.chunks.push(event.data);
        }
      };

      recorder.onerror = () => {
        this.onError?.("Ошибка записи голоса.");
      };

      recorder.onstop = () => {
        const duration = (Date.now() - this.startedAt) / 1000;
        this.lastDuration = duration;
        this._stopVoiceMonitor();
        this._stopTracks();

        if (duration < this.minDurationSeconds) {
          this.lastRecording = null;
          this.onStateChange?.({ isRecording: false, duration, hasRecording: false, mimeType: this.mimeType });
          this.onTooShort?.(duration);
          return;
        }

        const finalMime = this.mimeType || this.chunks?.[0]?.type || "audio/webm";
        const extension = extensionForMime(finalMime);
        const blob = new Blob(this.chunks, { type: finalMime });
        const timestamp = new Date().toISOString().replaceAll(":", "-");
        const file = new File([blob], `recording_${timestamp}.${extension}`, { type: finalMime });

        this.lastRecording = file;
        this.onStateChange?.({ isRecording: false, duration, hasRecording: true, mimeType: finalMime });
        this.onReady?.(file, duration);
      };

      recorder.start();
      this.onStateChange?.({ isRecording: true, duration: 0, hasRecording: Boolean(this.lastRecording), mimeType: this.mimeType });
      this.onVoiceLevel?.({ voiceDetected: false, level: 0 });
    } catch (error) {
      this._stopVoiceMonitor();
      this._stopTracks();
      this.onError?.(error?.message || "Не удалось получить доступ к микрофону.");
    }
  }

  async stop() {
    if (!this.recorder) return;
    if (this.recorder.state === "inactive") return;
    this.recorder.stop();
  }

  _stopTracks() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
  }

  _startVoiceMonitor() {
    if (!this.stream) return;
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return;

    try {
      this.audioContext = new AudioContextCtor();
      const source = this.audioContext.createMediaStreamSource(this.stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 1024;
      source.connect(this.analyser);
      this.voiceData = new Uint8Array(this.analyser.fftSize);
      this.lastVoiceEmitTs = 0;

      const loop = () => {
        if (!this.analyser || !this.voiceData) return;
        this.analyser.getByteTimeDomainData(this.voiceData);

        let energy = 0;
        for (let i = 0; i < this.voiceData.length; i += 1) {
          const centered = (this.voiceData[i] - 128) / 128;
          energy += centered * centered;
        }
        const rms = Math.sqrt(energy / this.voiceData.length);
        const voiceDetected = rms >= this.voiceThreshold;

        const now = performance.now();
        if (now - this.lastVoiceEmitTs >= 120) {
          this.onVoiceLevel?.({ voiceDetected, level: rms });
          this.lastVoiceEmitTs = now;
        }

        this.voiceRaf = window.requestAnimationFrame(loop);
      };

      this.voiceRaf = window.requestAnimationFrame(loop);
    } catch {
      // ignore analyzer errors, recording still works
    }
  }

  _stopVoiceMonitor() {
    if (this.voiceRaf) {
      window.cancelAnimationFrame(this.voiceRaf);
      this.voiceRaf = null;
    }
    this.analyser = null;
    this.voiceData = null;
    this.lastVoiceEmitTs = 0;
    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }
    this.onVoiceLevel?.({ voiceDetected: false, level: 0 });
  }
}
