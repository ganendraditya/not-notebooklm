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
      const step = diff > 80 ? Math.ceil(diff / 4) : (diff > 30 ? Math.ceil(diff / 6) : Math.min(diff, 2));
      displayed += target.slice(displayed.length, displayed.length + step);
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
