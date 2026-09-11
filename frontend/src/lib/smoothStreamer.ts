/**
 * Client-Side Smooth Streaming Typewriter.
 * Interpolates chunk bursts from SSE into a fluid, character/word-level stream
 * matching modern frontier chatbots (ChatGPT, Claude).
 */

export interface SmoothStreamerOptions {
  onUpdate: (displayedText: string) => void;
  onDone?: () => void;
  tickMs?: number;
}

export function createSmoothTextStreamer({
  onUpdate,
  onDone,
  tickMs = 20
}: SmoothStreamerOptions) {
  let target = "";
  let displayed = "";
  let isStreamDone = false;
  let intervalId: ReturnType<typeof setInterval> | null = null;

  function tick() {
    if (displayed.length < target.length) {
      const diff = target.length - displayed.length;
      // Adaptive velocity:
      // If backlog is high (> 80 chars), advance faster so we never lag behind
      // If close to frontier, step in gentle 2-3 char increments
      let step = Math.min(diff, 2);
      if (diff > 80) {
        step = Math.ceil(diff / 4);
      } else if (diff > 30) {
        step = Math.ceil(diff / 6);
      }

      let nextIndex = displayed.length + step;
      // Prevent splitting UTF-16 surrogate pairs (e.g. emojis or math symbols) across ticks
      const code = target.charCodeAt(nextIndex - 1);
      if (code >= 0xD800 && code <= 0xDBFF && nextIndex < target.length) {
        nextIndex++;
      }

      displayed = target.slice(0, nextIndex);
      onUpdate(displayed);
    } else if (isStreamDone) {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
      onDone?.();
    }
  }

  function ensureRunning() {
    if (intervalId === null) {
      intervalId = setInterval(tick, tickMs);
    }
  }

  return {
    pushDelta(chunk: string) {
      target += chunk;
      ensureRunning();
    },
    reset(newText: string = "") {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
      isStreamDone = false;
      target = newText;
      displayed = newText;
      onUpdate(displayed);
    },
    finish() {
      isStreamDone = true;
      ensureRunning();
      if (displayed.length >= target.length) {
        if (intervalId !== null) {
          clearInterval(intervalId);
          intervalId = null;
        }
        onDone?.();
      }
    },
    stop() {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    }
  };
}
