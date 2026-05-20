/**
 * Amplitude-based mouth driver.
 *
 * Reads RMS amplitude from a `MediaStream` / `<audio>` element / any
 * `AudioNode`-compatible source, low-pass filters it (one-pole, time
 * constant = `smoothing_ms`), and exposes a smoothed `mouthOpen` ∈ [0, 1].
 *
 * All Web Audio dependencies are looked up lazily so the test suite can
 * supply a stubbed `AudioContext` / `AnalyserNode`. No DOM access at
 * module-load time.
 */

export interface AmplitudeDriverOptions {
  /** Time constant for the one-pole low-pass, in ms. */
  smoothingMs: number;
  /** Linear gain applied to the raw RMS before clamping. */
  gain: number;
  /** Power curve applied after clamp — `> 1` makes small sounds quieter. */
  openCurve: number;
  /** Pluggable now-source so tests can drive time deterministically. */
  now?: () => number;
}

export interface AmplitudeDriver {
  /** Connect a source node (e.g. `MediaElementAudioSourceNode`). */
  connect(source: AudioNode): void;
  /** Disconnect any current source. */
  disconnect(): void;
  /** Sample once and return the smoothed mouthOpen ∈ [0, 1]. */
  tick(): number;
  /** Latest cached `mouthOpen`. */
  current(): number;
  /** Release internal nodes (idempotent). */
  dispose(): void;
}

const DEFAULT_FFT_SIZE = 1024;
const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v);

/**
 * Build an amplitude-based driver against the provided `AudioContext`.
 * The driver wires its own `AnalyserNode`; the caller `.connect(source)`s
 * a source node into it.
 */
export function createAmplitudeDriver(
  ctx: AudioContext,
  opts: AmplitudeDriverOptions,
): AmplitudeDriver {
  const analyser = ctx.createAnalyser();
  analyser.fftSize = DEFAULT_FFT_SIZE;
  analyser.smoothingTimeConstant = 0; // we smooth manually
  const buffer = new Uint8Array(analyser.fftSize);
  const now = opts.now ?? (() => performance.now());

  let lastSample = now();
  let smoothed = 0;
  let connectedSource: AudioNode | null = null;
  let disposed = false;

  return {
    connect(source: AudioNode): void {
      if (disposed) return;
      if (connectedSource && connectedSource !== source) {
        try {
          connectedSource.disconnect(analyser);
        } catch {
          // safe to ignore; the source may already be dead
        }
      }
      try {
        source.connect(analyser);
      } catch {
        // tolerate test stubs that throw on connect
      }
      connectedSource = source;
    },
    disconnect(): void {
      if (connectedSource) {
        try {
          connectedSource.disconnect(analyser);
        } catch {
          // ignore
        }
        connectedSource = null;
      }
    },
    tick(): number {
      if (disposed) return smoothed;
      analyser.getByteTimeDomainData(buffer);

      // RMS over the time-domain window. The buffer is 0..255 with 128
      // as silence, so we centre it around zero before squaring.
      let sumSq = 0;
      for (let i = 0; i < buffer.length; i += 1) {
        const sample = (buffer[i]! - 128) / 128;
        sumSq += sample * sample;
      }
      const rms = Math.sqrt(sumSq / Math.max(1, buffer.length));

      // Gain + curve + clamp.
      const shaped = clamp01(Math.pow(rms * opts.gain, opts.openCurve));

      // One-pole low-pass: x_new = x_old + α·(target - x_old) where
      // α = dt / (smoothingMs + dt). dt is the wall-clock interval
      // since the last tick.
      const t = now();
      const dt = Math.max(0, t - lastSample);
      lastSample = t;
      const tau = Math.max(1, opts.smoothingMs);
      const alpha = dt / (tau + dt);
      smoothed = smoothed + alpha * (shaped - smoothed);
      return smoothed;
    },
    current(): number {
      return smoothed;
    },
    dispose(): void {
      if (disposed) return;
      disposed = true;
      try {
        if (connectedSource) connectedSource.disconnect(analyser);
      } catch {
        // ignore
      }
      try {
        analyser.disconnect();
      } catch {
        // ignore
      }
      connectedSource = null;
    },
  };
}
