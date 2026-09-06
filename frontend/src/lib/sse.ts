/**
 * Utility to reliably consume Server-Sent Events (SSE) stream from fetch Response.
 */
export async function consumeSSEStream<T = any>(
  response: Response,
  onEvent: (event: T) => void | Promise<void>
): Promise<void> {
  if (!response.ok) {
    throw new Error(`Server returned status ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No readable stream body received from server");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      while (buffer.includes("\n\n")) {
        const splitIdx = buffer.indexOf("\n\n");
        const eventBlock = buffer.slice(0, splitIdx);
        buffer = buffer.slice(splitIdx + 2);

        const lines = eventBlock.split("\n");
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            try {
              const parsed = JSON.parse(trimmed.slice(6));
              if (parsed && (parsed.type === "ping" || parsed.type === "heartbeat")) {
                continue;
              }
              await onEvent(parsed);
            } catch (err) {
              console.error("[SSE Parser Error]:", err, "Raw line:", trimmed);
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
