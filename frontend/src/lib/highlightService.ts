/**
 * Highlight Grounding Service:
 * In-memory client cache & proactive background prefetcher.
 * Automatically fetches and stores exact AI evidence passages for citation buttons
 * before the user even clicks them, delivering instant 0ms highlight feedback.
 */

const highlightCache = new Map<string, string[]>();
const inFlightRequests = new Map<string, Promise<string[]>>();

export function computeClaimKey(chatId: string, docId: number, claim: string): string {
  const norm = (claim || "").trim().toLowerCase().replace(/\s+/g, " ");
  return `${chatId}:${docId}:${norm}`;
}

export function getCachedHighlightPassages(
  chatId: string,
  docId: number,
  claim: string
): string[] | undefined {
  const key = computeClaimKey(chatId, docId, claim);
  return highlightCache.get(key);
}

export function setCachedHighlightPassages(
  chatId: string,
  docId: number,
  claim: string,
  passages: string[]
): void {
  const key = computeClaimKey(chatId, docId, claim);
  highlightCache.set(key, passages);
}

export async function fetchOrPrefetchHighlights(
  backendUrl: string,
  chatId: string,
  docId: number,
  docNum: number | undefined,
  claim: string
): Promise<string[]> {
  const claimClean = (claim || "").trim();
  if (!claimClean || !chatId || !docId || !backendUrl) {
    return [];
  }

  const key = computeClaimKey(chatId, docId, claimClean);

  if (highlightCache.has(key)) {
    return highlightCache.get(key)!;
  }

  if (inFlightRequests.has(key)) {
    return inFlightRequests.get(key)!;
  }

  const promise = (async () => {
    try {
      const res = await fetch(`${backendUrl}/chats/${chatId}/highlight`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          claim: claimClean,
          doc_id: docId,
          doc_num: docNum,
        }),
      });

      if (!res.ok) {
        throw new Error(`Highlight request failed: ${res.status}`);
      }

      const data = await res.json();
      const passages: string[] = Array.isArray(data.passages) ? data.passages : [];
      if (passages.length > 0) {
        highlightCache.set(key, passages);
      }
      return passages;
    } catch {
      return [];
    } finally {
      inFlightRequests.delete(key);
    }
  })();

  inFlightRequests.set(key, promise);
  return promise;
}
