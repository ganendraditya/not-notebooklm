"use client";

import React, { useState, useRef, useMemo, useCallback, memo, useLayoutEffect, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { 
  ChevronDown, 
  Check, 
  Minus,
  Plus, 
  X,
  Loader2, 
  ExternalLink, 
  BookOpen, 
  Copy, 
  FileText,
  Table
} from "lucide-react";
import { ChatMessage } from "@/stores/chatStore";
import { Document as DocType, registerPendingCancelCallback, unregisterPendingCancelCallback, useDocumentStore } from "@/stores/documentStore";
import { parseCitationsInReactNode, CitationContext, enhanceTableCitations } from "./CitationParser";
import { useTranslation } from "@/lib/i18n";
import { consumeSSEStream } from "@/lib/sse";
import { Tooltip } from "@/components/ui/tooltip";
import { isMatchingPaper } from "@/lib/sourceUtils";

export interface AcademicCandidateSource {
  title?: string;
  year?: string | number;
  authors?: string[];
  journal?: string;
  doi?: string;
  url?: string;
  pdf_url?: string;
  snippet?: string;
  abstract?: string;
  is_oa?: boolean;
  citation_count?: number;
}

export interface InChatMessageProps {
  msg: ChatMessage;
  activeChatId: string | null;
  backendUrl: string;
  documents?: DocType[];
  onDocumentAdded?: (doc: DocType, targetChatId?: string) => void;
  onAddPendingSources?: (items: { id: string; filename: string; type: "file" | "doi"; status: "uploading" }[]) => void;
  onResolvePendingSource?: (pendingId: string) => void;
  onOpenDocument?: (doc: DocType, citationContext?: CitationContext) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  activeCitationKey?: string | null;
}

const TableRowContext = React.createContext<string>("");

function extractNodeText(node: any): string {
  if (!node) return "";
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractNodeText).filter(Boolean).join(" ");
  if (node.value) return node.value;
  if (node.children) return extractNodeText(node.children);
  if (node.props?.children) return extractNodeText(node.props.children);
  return "";
}

function extractTableRowText(node: any, children: any): string {
  if (node?.children && Array.isArray(node.children)) {
    const cellTexts = node.children
      .map((cellNode: any) => extractNodeText(cellNode).trim())
      .filter((txt: string) => txt.length > 0);
    if (cellTexts.length > 0) {
      return cellTexts.join(" | ");
    }
  }
  if (children) {
    const raw = extractNodeText(children);
    if (raw) return raw;
  }
  return "";
}

interface TableCellRendererProps {
  isHeader?: boolean;
  colIndex?: number;
  node?: any;
  documents?: DocType[];
  onOpenDocument?: (doc: DocType, citationContext?: CitationContext) => void;
  activeCitationKey?: string | null;
  citationMap?: Record<string, string[]>;
  children?: React.ReactNode;
  [key: string]: any;
}

const TableCellRenderer: React.FC<TableCellRendererProps> = ({
  isHeader = false,
  colIndex = 0,
  node,
  documents,
  onOpenDocument,
  activeCitationKey,
  citationMap,
  children,
  ...props
}) => {
  const cellRawText = extractNodeText(children);
  const cellClean = cellRawText
    .replace(/(?:\[(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*\]|(?:Dokumen|Document|Paper|Source)\s*\[?\d{1,3}\]?(?:\s*:|\b)|\bDokumen\s+\d{1,3}\b|\(\d{1,3}\))/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/^[|\s*#_:-]+|[|\s*#_:-]+$/g, "")
    .trim();

  // Column 0 is the document identity column (e.g. Doc # & Citation, Dokumen / Judul)
  const isDocColumn = !isHeader && colIndex === 0;

  // Never pass the entire multi-column rowContext as search context!
  // If this cell is the doc column or has no factual text, pass "" so no random highlighting occurs.
  const isGenericOrEmpty = isDocColumn || !cellClean || cellClean.length < 3 || /^(?:doc|dokumen|paper|sumber|ref|source)?\s*\[?\d*\]?$/i.test(cellClean);
  const contextToPass = isGenericOrEmpty ? "" : cellRawText;

  // Compute unique AST cell offset to ensure citation keys in different columns never collide
  const offset = node?.position?.start?.offset ?? (node?.position?.start ? `${node.position.start.line}_${node.position.start.column}` : undefined);
  const cellPrefix = isHeader ? `th_${offset ?? "h"}` : `td_${offset ?? "d"}`;

  // Extract alignment from props or node properties
  const align = props.align || props.style?.textAlign || node?.properties?.align || "left";
  const alignClass = 
    align === "right" ? "text-right" :
    align === "center" ? "text-center" :
    "text-left";

  if (isHeader) {
    return (
      <th 
        className={`py-2.5 px-3 font-semibold text-app-text text-xs align-top whitespace-nowrap ${alignClass}`} 
        {...props}
      >
        {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, contextToPass, citationMap, cellPrefix, isDocColumn)}
      </th>
    );
  }
  return (
    <td 
      className={`py-2.5 px-3 text-app-text-muted text-xs leading-relaxed align-top ${alignClass}`} 
      {...props}
    >
      {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, contextToPass, citationMap, cellPrefix, isDocColumn)}
    </td>
  );
};

const MarkdownTableBlock: React.FC<{ children?: React.ReactNode; [key: string]: any }> = ({ children, ...props }) => {
  const tableRef = React.useRef<HTMLTableElement>(null);
  const scrollContainerRef = React.useRef<HTMLDivElement>(null);
  const scrollPosRef = React.useRef<number>(0);
  const [copied, setCopied] = useState(false);

  // Preserve horizontal scroll position across re-renders or layout changes (e.g. sidebar toggle or citation click)
  useLayoutEffect(() => {
    if (scrollContainerRef.current && scrollPosRef.current > 0) {
      scrollContainerRef.current.scrollLeft = scrollPosRef.current;
    }
  });

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    scrollPosRef.current = e.currentTarget.scrollLeft;
  }, []);

  // Restore scrollLeft if window / sidebar causes container width resize
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onResize = () => {
      if (scrollPosRef.current > 0) {
        el.scrollLeft = scrollPosRef.current;
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const handleCopy = useCallback(async () => {
    if (!tableRef.current) return;
    try {
      const rows = Array.from(tableRef.current.querySelectorAll("tr"));
      if (rows.length === 0) return;

      const matrix = rows.map((r) =>
        Array.from(r.querySelectorAll("th, td")).map((cell) => {
          let text = cell.textContent || "";
          // Strip any stray HTML tags (e.g. </mark>, </blockquote>) that might leak into textContent
          text = text.replace(/<\/?[a-z0-9]+(?:\s+[^>]*)?>/gi, "");
          return text.replace(/\s+/g, " ").replace(/\|/g, "\\|").trim();
        })
      );

      // Construct clean Markdown table string
      const headerRow = matrix[0] ? `| ${matrix[0].join(" | ")} |` : "";
      const separatorRow = matrix[0] ? `| ${matrix[0].map(() => "---").join(" | ")} |` : "";
      const bodyRows = matrix.slice(1).map((r) => `| ${r.join(" | ")} |`).join("\n");
      const mdTable = `${headerRow}\n${separatorRow}\n${bodyRows}`.trim();

      await navigator.clipboard.writeText(mdTable);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy table:", err);
    }
  }, []);

  return (
    <div className="my-4 rounded-xl border border-app-border overflow-hidden shadow-sm bg-app-card/30">
      {/* Top integrated mini-toolbar */}
      <div className="flex items-center justify-between px-3 py-1 bg-app-surface/90 border-b border-app-border text-xs text-app-text-muted select-none">
        <div className="flex items-center text-app-text-dim">
          <Table size={13} className="text-app-text-dim shrink-0" />
        </div>
        <Tooltip content={copied ? "Copied!" : "Copy table"} side="top">
          <button
            type="button"
            onClick={handleCopy}
            aria-label="Copy table"
            className="p-1 rounded-md text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer"
          >
            {copied ? (
              <Check size={13} className="text-emerald-500 shrink-0" />
            ) : (
              <Copy size={13} className="shrink-0" />
            )}
          </button>
        </Tooltip>
      </div>

      <div 
        ref={scrollContainerRef}
        onScroll={(e) => {
          e.stopPropagation();
          handleScroll(e);
        }}
        onWheel={(e) => e.stopPropagation()}
        className="overflow-x-auto custom-scrollbar"
      >
        <table ref={tableRef} className="w-full text-left text-sm border-collapse bg-app-table-bg [&_td]:align-top [&_th]:align-top" {...props}>
          {children}
        </table>
      </div>
    </div>
  );
};

const MarkdownTableHeader: React.FC<{ children?: React.ReactNode; [key: string]: any }> = ({ children, ...props }) => (
  <thead className="bg-app-table-header text-app-text border-b border-app-border font-semibold select-none" {...props}>
    {children}
  </thead>
);

const MarkdownTableBody: React.FC<{ children?: React.ReactNode; [key: string]: any }> = ({ children, ...props }) => (
  <tbody className="divide-y divide-app-divider" {...props}>
    {children}
  </tbody>
);

const MarkdownTableRow: React.FC<{ node?: any; children?: React.ReactNode; [key: string]: any }> = ({ node, children, ...props }) => {
  const rowText = extractTableRowText(node, children);
  const indexedChildren = React.Children.map(children, (child, colIndex) => {
    if (React.isValidElement(child)) {
      return React.cloneElement(child as React.ReactElement<any>, { colIndex });
    }
    return child;
  });
  return (
    <TableRowContext.Provider value={rowText}>
      <tr className="hover:bg-app-item-hover transition-colors align-top" {...props}>
        {indexedChildren}
      </tr>
    </TableRowContext.Provider>
  );
};

export const InChatMessageComponent = memo(function InChatMessageComponent({ 
  msg, 
  activeChatId, 
  backendUrl, 
  documents = [],
  onDocumentAdded,
  onAddPendingSources,
  onResolvePendingSource,
  onOpenDocument,
  onEnsureChatSession,
  activeCitationKey
}: InChatMessageProps) {
  const { t } = useTranslation();
  const isUser = msg.role === "user";
  const { cleanContent, sources, citationMap } = useMemo(() => {
    const sourcesMatch = msg.content.match(/<!-- SOURCES_DATA:\s*([\s\S]*?)(?:-->|$)/);
    const citationMapMatch = msg.content.match(/<!-- CITATION_MAP:\s*([\s\S]*?)(?:-->|$)/);

    let clean = msg.content;
    let parsedSources: AcademicCandidateSource[] = [];
    let parsedCitationMap: Record<string, string[]> = {};
    
    if (sourcesMatch) {
      clean = clean.replace(/<!-- SOURCES_DATA:[\s\S]*?(?:-->|$)/gi, "").trim();
      try {
        const rawSources: AcademicCandidateSource[] = JSON.parse(sourcesMatch[1].replace(/-->.*$/, "").trim());
        if (Array.isArray(rawSources)) {
          const uniqueSources: AcademicCandidateSource[] = [];
          for (const s of rawSources) {
            if (!uniqueSources.some(existing => isMatchingPaper(s, existing))) {
              uniqueSources.push(s);
            }
          }
          parsedSources = uniqueSources;
        }
      } catch {
        // May be incomplete while streaming
      }
    }

    if (citationMapMatch) {
      clean = clean.replace(/<!-- CITATION_MAP:[\s\S]*?(?:-->|$)/gi, "").trim();
      try {
        // Robust JSON parse: strip markdown code fences, trailing commas
        let rawJson = citationMapMatch[1].replace(/-->.*$/, "").trim();
        rawJson = rawJson.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
        rawJson = rawJson.replace(/,\s*([\]}])/g, "$1"); // trailing commas
        parsedCitationMap = JSON.parse(rawJson);
      } catch {
        // May be incomplete while streaming
      }
    }

    // Clean any internal actions tag
    clean = clean.replace(/<!-- SOURCES_ACTION:[\s\S]*?-->/, "").trim();
    // Strip raw HTML anchor/target artifacts emitted by LLMs (e.g. <a id="doc1"></a>, <a name="...">, etc.)
    // If it's a wrapper like <a id="doc1">inner</a>, preserve inner content; if empty, drop entirely.
    clean = clean.replace(/<a\b(?:\s+[^>]*)?>([\s\S]*?)<\/a>/gi, (match, innerText) => {
      // If it's an anchor without href or with internal jump anchor href="#..."
      if (!/\bhref\s*=/i.test(match) || /\bhref\s*=\s*["']?#/i.test(match)) {
        return innerText;
      }
      return match;
    });
    // Remove self-closing or unclosed anchor target tags like <a id="doc1"/> or <a id="doc1">
    clean = clean.replace(/<a\b[^>]*\b(?:id|name)=[^>]*\/?>/gi, "");
    clean = clean.replace(/<\/a>/gi, "");
    // Remove empty span/div placeholders with ids/names (e.g. <span id="doc1"></span>)
    clean = clean.replace(/<(?:span|div)\b[^>]*\b(?:id|name)=[^>]*>\s*<\/(?:span|div)>/gi, "");

    // Strip fake citation markdown links emitted by LLMs (e.g. [[1]](#doc1), [1](#doc1), [(1)](#doc1), [[M-01]](#ref-01), [1](url))
    // Converts them to clean standard bracketed citations: [1], [M-01], [Dokumen 1] so they never render as <a target="_blank">
    clean = clean.replace(/\[{0,2}\(?((?:Dokumen|Document|Doc|Paper|Source|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3})*)\)?\]{0,2}\((?:#[^)]*|https?:\/\/[^)]*)\)/gi, "[$1]");

    // Strip raw HTML quote/highlight artifacts emitted by LLMs (e.g. <blockquote><mark>"..."</mark></blockquote>, </mark>, etc.)
    // Preserves the inner text verbatim while stripping the HTML tags
    clean = clean.replace(/<\/?(?:mark|blockquote|q|cite|font|center|small|big)\b[^>]*>/gi, "");

    // Ensure all table cells mapped to documents have granular clickable citations
    clean = enhanceTableCitations(clean);
    return { cleanContent: clean, sources: parsedSources, citationMap: parsedCitationMap };
  }, [msg.content]);

  const isDuplicateSource = useCallback((src: AcademicCandidateSource) => {
    if (!documents || documents.length === 0) return false;
    return documents.some(doc => isMatchingPaper(src, doc));
  }, [documents]);

  const [userSelectionOverrides, setUserSelectionOverrides] = useState<Record<number, boolean>>({});
  const [isImporting, setIsImporting] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const isSourceChecked = useCallback((src: AcademicCandidateSource, index: number) => {
    if (isDuplicateSource(src)) return false;
    if (userSelectionOverrides[index] !== undefined) {
      return userSelectionOverrides[index];
    }
    return true;
  }, [userSelectionOverrides, isDuplicateSource]);

  const toggleSelectAll = () => {
    if (isImporting) return;
    const novelIndices = sources.map((s, i) => (!isDuplicateSource(s) ? i : -1)).filter(i => i !== -1);
    if (novelIndices.length === 0) return;

    // Mazhab A: if ALL or PARTIALLY selected, clicking deselects all. Only if 0 selected, clicking selects all.
    const hasAnyNovelSelected = novelIndices.some(i => isSourceChecked(sources[i], i));
    const nextState = !hasAnyNovelSelected;
    
    const updated = { ...userSelectionOverrides };
    novelIndices.forEach(i => {
      updated[i] = nextState;
    });
    setUserSelectionOverrides(updated);
  };

  const [importProgress, setImportProgress] = useState<{ current: number; total: number } | null>(null);
  const isMountedRef = useRef(true);
  const activeItemControllersRef = useRef<Map<string, AbortController>>(new Map());
  const cancelledPendingIdsRef = useRef<Set<string>>(new Set());
  const isBatchCancelledRef = useRef<boolean>(false);
  const pendingItemsRef = useRef<{ id: string }[]>([]);
  const onResolvePendingSourceRef = useRef(onResolvePendingSource);
  onResolvePendingSourceRef.current = onResolvePendingSource;

  useEffect(() => {
    isMountedRef.current = true;
    const controllersMap = activeItemControllersRef.current;
    return () => {
      isMountedRef.current = false;
      isBatchCancelledRef.current = true;
      controllersMap.forEach(c => c.abort());
      controllersMap.clear();
      pendingItemsRef.current.forEach(p => {
        unregisterPendingCancelCallback(p.id);
        onResolvePendingSourceRef.current?.(p.id);
      });
      pendingItemsRef.current = [];
    };
  }, []);

  const handleImport = async () => {
    const toImport = sources.filter((src, i) => !isDuplicateSource(src) && isSourceChecked(src, i));
    if (toImport.length === 0) return;

    isBatchCancelledRef.current = false;
    cancelledPendingIdsRef.current.clear();
    activeItemControllersRef.current.clear();

    setIsImporting(true);
    setImportProgress({ current: 1, total: toImport.length });

    // Register pending placeholder sources immediately in the sidebar so circular spinners appear
    const pendingItems = toImport.map((src, idx) => ({
      id: `pending-import-${Date.now()}-${idx}-${Math.random().toString(36).slice(2, 6)}`,
      filename: `${(src.title || src.doi || "Research Paper").trim()}.pdf`,
      type: "doi" as const,
      doi: src.doi,
      status: "uploading" as const,
    }));
    pendingItemsRef.current = pendingItems;
    onAddPendingSources?.(pendingItems);

    let currentChatId = activeChatId;

    // Register cancellation callback for each pending item in the sidebar
    pendingItems.forEach((p) => {
      registerPendingCancelCallback(p.id, () => {
        cancelledPendingIdsRef.current.add(p.id);
        const controller = activeItemControllersRef.current.get(p.id);
        if (controller) {
          controller.abort();
          activeItemControllersRef.current.delete(p.id);
        }
        onResolvePendingSource?.(p.id);

        const activeItems = pendingItems.filter(item => !cancelledPendingIdsRef.current.has(item.id));
        if (activeItems.length === 0) {
          // If all items were cancelled by the user in the sidebar, terminate batch state immediately
          isBatchCancelledRef.current = true;
          if (isMountedRef.current) {
            setIsImporting(false);
            setImportProgress(null);
          }
        } else if (isMountedRef.current) {
          // Instantly adjust active total and current active index in the button counter (e.g. from x/5 to x/4)
          setImportProgress(prev => {
            if (!prev) return null;
            const newTotal = activeItems.length;
            const newCurrent = Math.min(Math.max(1, prev.current), newTotal);
            return { current: newCurrent, total: newTotal };
          });
        }
      });
    });

    try {
      if (!currentChatId && onEnsureChatSession) {
        currentChatId = await onEnsureChatSession(toImport[0]?.title || "Research Paper");
      }
      if (!currentChatId || isBatchCancelledRef.current) return;

      // Concurrency Pool: Process up to 4 papers concurrently for 3-4x throughput while strictly adhering to academic API rate limits
      const CONCURRENCY = Math.min(4, toImport.length);
      let nextIndex = 0;
      let completedCount = 0;

      const runWorker = async () => {
        while (nextIndex < toImport.length && !isBatchCancelledRef.current) {
          const currentIndex = nextIndex++;
          const src = toImport[currentIndex];
          const pending = pendingItems[currentIndex];

          // If user already clicked cancel on this item, skip it completely!
          if (cancelledPendingIdsRef.current.has(pending.id)) {
            onResolvePendingSourceRef.current?.(pending.id);
            unregisterPendingCancelCallback(pending.id);
            continue;
          }

          const itemController = new AbortController();
          activeItemControllersRef.current.set(pending.id, itemController);
          let createdDocId: number | null = null;

          try {
            const res = await fetch(`${backendUrl}/chats/${currentChatId}/import_sources_stream`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ sources: [src] }),
              signal: itemController.signal
            });

            if (!res.ok) {
              const errData = await res.json().catch(() => null);
              throw new Error(errData?.detail || `Server returned ${res.status}`);
            }

            await consumeSSEStream(res, (data: any) => {
              if (cancelledPendingIdsRef.current.has(pending.id) || isBatchCancelledRef.current) return;

              if (data.type === "progress" && data.doc) {
                createdDocId = data.doc.id;
                if (!cancelledPendingIdsRef.current.has(pending.id) && !isBatchCancelledRef.current) {
                  onDocumentAdded?.(data.doc as DocType, currentChatId || undefined);
                }
              }
            });
          } catch (err: any) {
            if (err.name === "AbortError" || cancelledPendingIdsRef.current.has(pending.id)) {
              // If aborted, delete any created document from backend so zero trace remains
              if (createdDocId && currentChatId) {
                fetch(`${backendUrl}/chats/${currentChatId}/documents/${createdDocId}`, { method: "DELETE" }).catch(() => {});
                useDocumentStore.getState().updateDocumentsList(prev => prev.filter(d => d.id !== createdDocId));
              }
            } else {
              console.error("Import source failed:", err);
            }
          } finally {
            activeItemControllersRef.current.delete(pending.id);
            onResolvePendingSourceRef.current?.(pending.id);
            unregisterPendingCancelCallback(pending.id);
            completedCount++;
            if (isMountedRef.current && !isBatchCancelledRef.current) {
              setImportProgress({
                current: Math.min(completedCount, toImport.length),
                total: toImport.length
              });
            }
          }
        }
      };

      const workers = Array.from({ length: CONCURRENCY }, () => runWorker());
      await Promise.all(workers);

      if (isMountedRef.current && !isBatchCancelledRef.current) {
        setUserSelectionOverrides({});
      }
    } catch (e: any) {
      if (e.name === "AbortError" || isBatchCancelledRef.current) {
        return;
      }
      console.error("Import sources failed:", e);
    } finally {
      pendingItems.forEach(p => {
        onResolvePendingSource?.(p.id);
        unregisterPendingCancelCallback(p.id);
      });
      pendingItemsRef.current = [];
      activeItemControllersRef.current.clear();
      if (isMountedRef.current) {
        setIsImporting(false);
        setImportProgress(null);
      }
    }
  };

  const handleCancelImport = () => {
    isBatchCancelledRef.current = true;
    activeItemControllersRef.current.forEach(c => c.abort());
    activeItemControllersRef.current.clear();
    if (isMountedRef.current) {
      setIsImporting(false);
      setImportProgress(null);
    }
  };

  const novelSourcesCount = useMemo(() => sources.filter(s => !isDuplicateSource(s)).length, [sources, isDuplicateSource]);
  const selectedCount = useMemo(() => sources.filter((s, i) => !isDuplicateSource(s) && isSourceChecked(s, i)).length, [sources, isDuplicateSource, isSourceChecked]);
  const allNovelSelected = useMemo(() => {
    const novelIndices = sources.map((s, i) => (!isDuplicateSource(s) ? i : -1)).filter(i => i !== -1);
    return novelIndices.length > 0 && novelIndices.every(i => isSourceChecked(sources[i], i));
  }, [sources, isDuplicateSource, isSourceChecked]);
  const isPartiallySelected = selectedCount > 0 && selectedCount < novelSourcesCount;

  return (
    <div className={`mb-3 flex ${isUser ? "justify-end" : "justify-start w-full"} font-sans group`}>
      <div 
        className={`relative leading-relaxed tracking-wide ${
          isUser 
            ? "inline-block max-w-[95%] sm:max-w-[85%] bg-app-user-bubble border border-app-border text-app-text px-5 py-3.5 rounded-[1.5rem] rounded-tr-sm shadow-md"
            : "w-full max-w-full text-app-text"
        }`}
      >
        {isUser && msg.attachments && msg.attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2 pb-2 border-b border-app-divider">
            {msg.attachments.map((att, idx) => {
              const fileHref = att.url?.startsWith("http") ? att.url : `${backendUrl}${att.url || ""}`;
              return (
                <a 
                  key={idx} 
                  href={fileHref} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="flex items-center gap-2 p-1.5 pr-3 rounded-lg bg-black/5 dark:bg-black/40 border border-app-border hover:border-app-border-strong transition-colors"
                >
                  {att.type === "image" ? (
                    <div className="w-10 h-10 rounded shrink-0 overflow-hidden bg-black/10 dark:bg-black/60">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={fileHref} alt={att.filename} className="w-full h-full object-cover" />
                    </div>
                  ) : (
                    <div className="w-10 h-10 rounded shrink-0 bg-app-item-hover flex items-center justify-center">
                      <FileText size={18} className="text-app-text-muted" />
                    </div>
                  )}
                  <span className="text-[11px] text-app-text font-medium truncate max-w-[150px]">{att.filename}</span>
                </a>
              );
            })}
          </div>
        )}

    <div className="w-full space-y-2 min-w-0 break-words">
      {/* 1. Main Markdown Text Content */}
      <div className="prose dark:prose-invert max-w-none text-[16px] leading-[1.65] break-words [word-break:break-word] text-app-text">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
          components={{
            p: ({ node, children, ...props }: any) => {
              const fullText = extractNodeText(node || children);
              const offset = node?.position?.start?.offset ?? (node?.position?.start ? `${node.position.start.line}_${node.position.start.column}` : undefined);
              const prefix = offset !== undefined ? `p_${offset}` : "p";
              return (
                <p className="mb-2 last:mb-0 text-app-text leading-[1.65]" {...props}>
                  {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, fullText, citationMap, prefix)}
                </p>
              );
            },
            h1: ({ node, children, ...props }: any) => {
              const fullText = extractNodeText(node || children);
              const offset = node?.position?.start?.offset ?? (node?.position?.start ? `${node.position.start.line}_${node.position.start.column}` : undefined);
              const prefix = offset !== undefined ? `h1_${offset}` : "h1";
              return (
                <h1 className="text-2xl font-bold text-app-text mt-5 mb-2.5 tracking-tight" {...props}>
                  {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, fullText, citationMap, prefix)}
                </h1>
              );
            },
            h2: ({ node, children, ...props }: any) => {
              const fullText = extractNodeText(node || children);
              const offset = node?.position?.start?.offset ?? (node?.position?.start ? `${node.position.start.line}_${node.position.start.column}` : undefined);
              const prefix = offset !== undefined ? `h2_${offset}` : "h2";
              return (
                <h2 className="text-xl font-bold text-app-text mt-4 mb-2 tracking-tight" {...props}>
                  {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, fullText, citationMap, prefix)}
                </h2>
              );
            },
            h3: ({ node, children, ...props }: any) => {
              const fullText = extractNodeText(node || children);
              const offset = node?.position?.start?.offset ?? (node?.position?.start ? `${node.position.start.line}_${node.position.start.column}` : undefined);
              const prefix = offset !== undefined ? `h3_${offset}` : "h3";
              return (
                <h3 className="text-lg font-semibold text-app-text mt-3 mb-1.5" {...props}>
                  {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, fullText, citationMap, prefix)}
                </h3>
              );
            },
            ul: ({ children }: any) => <ul className="list-disc pl-6 my-2.5 space-y-1.5 text-app-text">{children}</ul>,
            ol: ({ children }: any) => <ol className="list-decimal pl-8 my-2.5 space-y-1.5 text-app-text">{children}</ol>,
            li: ({ node, children, ...props }: any) => {
              const fullText = extractNodeText(node || children);
              const offset = node?.position?.start?.offset ?? (node?.position?.start ? `${node.position.start.line}_${node.position.start.column}` : undefined);
              const prefix = offset !== undefined ? `li_${offset}` : "li";
              return (
                <li className="leading-[1.65]" {...props}>
                  {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, fullText, citationMap, prefix)}
                </li>
              );
            },
            em: ({ children }) => <em className="italic">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "em")}</em>,
            strong: ({ children }) => <strong className="font-semibold text-app-text">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "strong")}</strong>,
            a: ({ href, children, ...props }: any) => {
              const isInternalAnchor = !href || href.startsWith("#");
              const linkText = extractNodeText(children).trim();
              const isCitationLike = /(?:\[{1,2}|\()?(?:Dokumen|Document|Doc|Paper|Source|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3})*(?:\]{1,2}|\))?/i.test(linkText);

              // If it's a citation link or internal anchor, unwrap it completely so no <a> target="_blank" wraps it!
              if (isCitationLike || isInternalAnchor) {
                return <>{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "a")}</>;
              }

              return (
                <a 
                  href={href} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 underline font-medium break-all"
                  {...props}
                >
                  {children}
                </a>
              );
            },
            table: MarkdownTableBlock,
            thead: MarkdownTableHeader,
            tbody: MarkdownTableBody,
            tr: MarkdownTableRow,
            th: ({ node, children, colIndex, ...props }: any) => (
              <TableCellRenderer
                isHeader={true}
                colIndex={colIndex}
                node={node}
                documents={documents}
                onOpenDocument={onOpenDocument}
                activeCitationKey={activeCitationKey}
                citationMap={citationMap}
                {...props}
              >
                {children}
              </TableCellRenderer>
            ),
            td: ({ node, children, colIndex, ...props }: any) => (
              <TableCellRenderer
                isHeader={false}
                colIndex={colIndex}
                node={node}
                documents={documents}
                onOpenDocument={onOpenDocument}
                activeCitationKey={activeCitationKey}
                citationMap={citationMap}
                {...props}
              >
                {children}
              </TableCellRenderer>
            ),
            blockquote: ({ node, children, ...props }: any) => {
              const fullText = extractNodeText(node || children);
              const offset = node?.position?.start?.offset ?? (node?.position?.start ? `${node.position.start.line}_${node.position.start.column}` : undefined);
              const prefix = offset !== undefined ? `bq_${offset}` : "bq";
              return (
                <blockquote className="border-l-2 border-blue-500 pl-4 py-1.5 my-3 text-app-text-muted bg-blue-500/5 rounded-r-lg italic" {...props}>
                  {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, fullText, citationMap, prefix)}
                </blockquote>
              );
            },
            pre: ({ children }: any) => (
              <div className="relative group my-3">
                <pre 
                  onScroll={(e) => e.stopPropagation()}
                  onWheel={(e) => e.stopPropagation()}
                  className="bg-app-code-bg p-3.5 rounded-xl overflow-x-auto text-xs text-app-text font-mono border border-app-border custom-scrollbar"
                >
                  {children}
                </pre>
              </div>
            ),
            code: ({ inline, className, children, ...props }: any) => {
              if (inline) {
                return (
                  <code className="bg-app-item-hover text-blue-600 dark:text-blue-300 px-1.5 py-0.5 rounded text-xs font-mono break-all" {...props}>
                    {children}
                  </code>
                );
              }
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            }
          }}
        >
          {cleanContent}
        </ReactMarkdown>
      </div>

      {/* 2. Embedded Interactive Paper Source Cards */}
      {sources.length > 0 && (
        <div className="mt-4 rounded-2xl bg-app-card border border-app-border overflow-hidden shadow-lg animate-in fade-in duration-200">
          <div 
            className="p-3.5 px-4 bg-app-surface flex items-center justify-between cursor-pointer select-none hover:bg-app-card-hover transition-colors border-b border-app-divider"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-app-text">
                Report &amp; Outside sources ({sources.length})
              </span>
            </div>
            <div className="flex items-center gap-2 text-app-text-muted">
              <ChevronDown size={16} className={`transition-transform duration-200 ${isCollapsed ? "-rotate-90" : ""}`} />
            </div>
          </div>

          {!isCollapsed && (
            <>
              <div className="pl-4 pr-[22px] py-2 bg-app-surface border-b border-app-divider flex items-center justify-between text-xs text-app-text-muted">
                <span className="text-app-text-muted">{t('chat.researchFound')}</span>
                {novelSourcesCount > 0 && (
                  <div 
                    onClick={(e) => { e.stopPropagation(); if (!isImporting) toggleSelectAll(); }}
                    className={`flex items-center gap-2 select-none ${
                      isImporting ? "opacity-40 cursor-not-allowed" : "cursor-pointer group/selectall"
                    }`}
                  >
                    <span className="text-[11px] font-medium text-app-text-muted group-hover/selectall:text-app-text transition-colors">
                      {(allNovelSelected || isPartiallySelected)
                        ? (t('right.unselectAll') || "Deselect All")
                        : (t('right.selectAll') || "Select All")}
                    </span>
                    <button 
                      type="button"
                      disabled={isImporting}
                      className={`w-4 h-4 rounded border flex items-center justify-center transition-colors shrink-0 ${
                        isImporting ? "cursor-not-allowed" : "cursor-pointer"
                      } ${
                        allNovelSelected || isPartiallySelected
                          ? "bg-blue-600 border-blue-600 text-white"
                          : "border-app-border-strong bg-transparent group-hover/selectall:border-gray-400"
                      }`}
                      aria-label={(allNovelSelected || isPartiallySelected) ? (t('right.unselectAll') || "Deselect All") : (t('right.selectAll') || "Select All")}
                    >
                      {allNovelSelected ? (
                        <Check size={11} strokeWidth={3} />
                      ) : isPartiallySelected ? (
                        <Minus size={11} strokeWidth={3} />
                      ) : null}
                    </button>
                  </div>
                )}
              </div>

              <div 
                onScroll={(e) => e.stopPropagation()}
                onWheel={(e) => e.stopPropagation()}
                className="max-h-[360px] overflow-y-auto divide-y divide-app-divider p-1 custom-scrollbar"
              >
                {sources.map((src, i) => {
                  const isAlreadyAdded = isDuplicateSource(src);
                  const isChecked = isAlreadyAdded || isSourceChecked(src, i);
                  return (
                    <div 
                      key={i} 
                      onClick={() => {
                        if (!isAlreadyAdded && !isImporting) {
                          setUserSelectionOverrides(prev => ({ ...prev, [i]: !isSourceChecked(src, i) }));
                        }
                      }}
                      className={`p-3 px-3.5 flex items-start justify-between gap-3 transition-colors rounded-xl m-1 ${
                        isAlreadyAdded 
                          ? "bg-emerald-500/[0.04] border border-emerald-500/10 cursor-default" 
                          : isImporting
                            ? "opacity-60 cursor-not-allowed"
                            : isChecked 
                              ? "bg-app-item-hover cursor-pointer" 
                              : "hover:bg-app-item-hover cursor-pointer"
                      }`}
                    >
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className={`p-2 rounded-lg shrink-0 mt-0.5 ${
                          isAlreadyAdded ? "bg-emerald-500/10 text-emerald-500" : "bg-blue-500/10 text-blue-500"
                        }`}>
                          <BookOpen size={16} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline gap-2 flex-wrap">
                            <h4 className="text-xs font-semibold text-app-text leading-snug line-clamp-2">
                              {src.title}
                            </h4>
                            {src.year && src.year !== "N/A" && (
                              <span className="text-[11px] text-app-text-dim shrink-0">
                                ({src.year})
                              </span>
                            )}
                            {isAlreadyAdded && (
                              <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded-full shrink-0">
                                In Sources
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            {src.url ? (
                              <a 
                                href={src.url} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                onClick={(e) => e.stopPropagation()}
                                className="text-[11px] text-blue-500 hover:text-blue-600 hover:underline flex items-center gap-1 shrink-0"
                              >
                                <span>{src.doi ? `DOI: ${src.doi}` : "Journal Link"}</span>
                                <ExternalLink size={10} />
                              </a>
                            ) : src.doi ? (
                              <span className="text-[11px] text-app-text-dim font-mono">
                                DOI: {src.doi}
                              </span>
                            ) : null}
                          </div>
                          {src.snippet && (
                            <p className="text-[11px] text-app-text-muted line-clamp-1 leading-normal mt-0.5">
                              {src.snippet}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className={`w-4 h-4 rounded border mt-1 flex items-center justify-center shrink-0 transition-colors ${
                        isAlreadyAdded 
                          ? "bg-emerald-600/30 border-emerald-500/40 text-emerald-600 dark:text-emerald-300"
                          : isChecked 
                            ? "bg-blue-600 border-blue-600 text-white" 
                            : "border-app-border-strong bg-transparent"
                      }`}>
                        {(isAlreadyAdded || isChecked) && <Check size={11} strokeWidth={3} />}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="p-3 px-4 bg-app-surface border-t border-app-divider flex items-center justify-between">
                <span className="text-xs text-app-text-muted font-medium">
                  {selectedCount}/{novelSourcesCount} new selected
                </span>

                <button
                  type="button"
                  onClick={isImporting ? handleCancelImport : handleImport}
                  disabled={!isImporting && selectedCount === 0}
                  className={`h-8 w-[180px] shrink-0 rounded-full text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer transition-colors border-0 outline-none select-none ${
                    isImporting
                      ? "bg-blue-600 hover:bg-red-600 text-white shadow-md group/cancelbtn"
                      : "bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
                  }`}
                  title={isImporting ? (t('chat.cancelAdding') || "Cancel adding") : undefined}
                >
                  {isImporting ? (
                    <>
                      <span className="flex items-center justify-center gap-1.5 group-hover/cancelbtn:hidden whitespace-nowrap">
                        <Loader2 size={12} className="animate-spin shrink-0" />
                        <span>{importProgress ? `Adding ${importProgress.current}/${importProgress.total}...` : "Adding sources..."}</span>
                      </span>
                      <span className="hidden group-hover/cancelbtn:flex items-center justify-center gap-1.5 text-white whitespace-nowrap">
                        <X size={12} strokeWidth={2.5} className="shrink-0" />
                        <span>{t('chat.cancelAdding') || "Cancel adding"}</span>
                      </span>
                    </>
                  ) : (
                    <span className="flex items-center justify-center gap-1.5 whitespace-nowrap">
                      <Plus size={13} className="shrink-0" />
                      <span>{t('chat.addToSources').replace('{count}', selectedCount > 0 ? `${selectedCount} ` : "")}</span>
                    </span>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
    </div>
    </div>
  );
});
