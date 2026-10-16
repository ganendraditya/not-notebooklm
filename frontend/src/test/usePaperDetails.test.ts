import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getCachedPaperDetails,
  prefetchDocumentContent,
  setCachedPaperDetails,
  updateCachedPaperTitle,
  type PaperDetailData,
} from "@/hooks/usePaperDetails";

describe("paper detail cache title synchronization", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("updates only the cached entry for the renamed source", () => {
    const paper: PaperDetailData = {
      id: 947,
      filename: "paper-b.pdf",
      type: "pdf",
      title: "Paper B",
      authors: [],
      publication_date: "",
      year: "",
      journal: "",
      journal_metric: "",
      citations: 0,
      doi: "",
      url: "",
      pdf_url: "",
      abstract: "",
      content: "",
    };
    setCachedPaperDetails("rename-cache-chat", paper.id, paper);

    updateCachedPaperTitle("rename-cache-chat", paper.id, "Evaluation Dataset");

    expect(getCachedPaperDetails("rename-cache-chat", paper.id)?.title).toBe("Evaluation Dataset");
    expect(getCachedPaperDetails("other-chat", paper.id)).toBeUndefined();
  });

  it("keeps a rename when an older in-flight prefetch resolves afterward", async () => {
    const chatId = "rename-cache-inflight-chat";
    const docId = 948;
    let resolveFetch: ((response: Response) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }))
    );

    const pendingFetch = prefetchDocumentContent("http://backend", chatId, docId);
    updateCachedPaperTitle(chatId, docId, "Evaluation Dataset");
    if (!resolveFetch) throw new Error("Expected the prefetch request to start.");
    resolveFetch(new Response(JSON.stringify({
      id: docId,
      filename: "paper-b.pdf",
      type: "pdf",
      title: "Paper B",
      authors: [],
      publication_date: "",
      year: "",
      journal: "",
      journal_metric: "",
      citations: 0,
      doi: "",
      url: "",
      pdf_url: "",
      abstract: "",
      content: "",
    }), { status: 200 }));

    const response = await pendingFetch;

    expect(response?.title).toBe("Evaluation Dataset");
    expect(getCachedPaperDetails(chatId, docId)?.title).toBe("Evaluation Dataset");
  });
});
