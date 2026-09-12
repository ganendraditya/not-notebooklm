import { describe, it, expect } from "vitest";
import { consumeSSEStream } from "../lib/sse";

describe("consumeSSEStream", () => {
  it("processes multi-line SSE data and handles chunked buffers", async () => {
    const ssePayload =
      'data: {"type": "status", "text": "Analyzing query..."}\n\n' +
      'data: {"type": "done", "data": "Hello world"}\n\n';

    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(ssePayload));
        controller.close();
      }
    });

    const mockResponse = new Response(stream, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" }
    });

    const events: any[] = [];
    await consumeSSEStream(mockResponse, (event) => {
      events.push(event);
    });

    expect(events.length).toBe(2);
    expect(events[0].type).toBe("status");
    expect(events[0].text).toBe("Analyzing query...");
    expect(events[1].type).toBe("done");
    expect(events[1].data).toBe("Hello world");
  });

  it("throws an error for non-200 responses", async () => {
    const mockResponse = new Response("Not Found", { status: 404 });
    await expect(consumeSSEStream(mockResponse, () => {})).rejects.toThrow("Server returned status 404");
  });
});
