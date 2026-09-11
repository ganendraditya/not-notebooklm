import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createSmoothTextStreamer } from "@/lib/smoothStreamer";

describe("createSmoothTextStreamer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("smoothly streams incoming tokens without splitting surrogate pairs", () => {
    const onUpdate = vi.fn();
    const onDone = vi.fn();
    const streamer = createSmoothTextStreamer({
      onUpdate,
      onDone,
      tickMs: 20,
    });

    // Contains surrogate pair (emoji 🚀 and math symbol 𝒪)
    streamer.pushDelta("Fast 🚀 and 𝒪(n)");
    streamer.finish();

    // Fast-forward all timers
    vi.runAllTimers();

    expect(onDone).toHaveBeenCalled();
    const lastCall = onUpdate.mock.calls[onUpdate.mock.calls.length - 1][0];
    expect(lastCall).toBe("Fast 🚀 and 𝒪(n)");

    // Ensure no intermediate call has a broken replacement char or split surrogate
    for (const call of onUpdate.mock.calls) {
      const text = call[0];
      expect(text).not.toContain("\uFFFD");
    }
  });

  it("resets correctly and clears active intervals without leaking stream state", () => {
    const onUpdate = vi.fn();
    const onDone = vi.fn();
    const streamer = createSmoothTextStreamer({
      onUpdate,
      onDone,
      tickMs: 20,
    });

    streamer.pushDelta("First Stream");
    streamer.finish();

    // Reset before running timers
    streamer.reset("New Stream");
    expect(onUpdate).toHaveBeenCalledWith("New Stream");

    // Push new delta and finish
    streamer.pushDelta(" Continued");
    streamer.finish();

    vi.runAllTimers();

    expect(onDone).toHaveBeenCalledTimes(1);
    const lastCall = onUpdate.mock.calls[onUpdate.mock.calls.length - 1][0];
    expect(lastCall).toBe("New Stream Continued");
  });
});
