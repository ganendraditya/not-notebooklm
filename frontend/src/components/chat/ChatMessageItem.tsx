"use client";

import React, { useState, useMemo, useCallback, memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  ChevronDown, 
  Check, 
  Plus, 
  Loader2, 
  ExternalLink, 
  BookOpen, 
  Copy, 
  Pencil, 
  FileText
} from "lucide-react";
import { ChatMessage } from "@/stores/chatStore";
import { Document as DocType } from "@/stores/documentStore";
import { parseCitationsInReactNode, CitationContext } from "./CitationParser";
import { useTranslation } from "@/lib/i18n";
import { consumeSSEStream } from "@/lib/sse";
import { Tooltip } from "@/components/ui/tooltip";

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
  node,
  documents,
  onOpenDocument,
  activeCitationKey,
  citationMap,
  children,
  ...props
}) => {
  const rowContext = React.useContext(TableRowContext);
  const cellRawText = extractNodeText(children);
  const cellClean = cellRawText
    .replace(/(?:\[(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*\]|(?:Dokumen|Document|Paper|Source)\s*\[?\d{1,3}\]?(?:\s*:|\b)|\bDokumen\s+\d{1,3}\b|\(\d{1,3}\))/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/^[|\s*#_:-]+|[|\s*#_:-]+$/g, "")
    .trim();

  // If this cell has specific content (e.g. "1.500 ulasan produk", "Naïve Bayes + TF-IDF", "77,78%"), pass cellRawText!
  // If this cell has NO factual text (e.g. it's just "[1]" in the Source column or generic "Doc 1"), pass rowContext!
  const isGenericOrEmpty = !cellClean || cellClean.length < 3 || /^(?:doc|dokumen|paper|sumber|ref|source)?\s*\[?\d*\]?$/i.test(cellClean);
  const contextToPass = isGenericOrEmpty ? rowContext : cellRawText;

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
        className={`py-2.5 px-3 font-semibold text-app-text text-xs tracking-wider uppercase align-top whitespace-nowrap last:pr-9 ${alignClass}`} 
        {...props}
      >
        {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, contextToPass, citationMap, cellPrefix)}
      </th>
    );
  }
  return (
    <td 
      className={`py-2.5 px-3 text-app-text-muted text-xs leading-relaxed align-top ${alignClass}`} 
      {...props}
    >
      {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, contextToPass, citationMap, cellPrefix)}
    </td>
  );
};

const MarkdownTableBlock: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const tableRef = React.useRef<HTMLTableElement>(null);
  const [copied, setCopied] = useState(false);

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
    <div className="relative my-4 group/tbl">
      {/* Top right corner copy button */}
      <div className="absolute top-2 right-2 z-10 flex items-center">
        <Tooltip content={copied ? "Copied!" : "Copy table"} side="top">
          <button
            type="button"
            onClick={handleCopy}
            aria-label="Copy table"
            className="p-1.5 rounded-md text-app-text-muted hover:text-app-text hover:bg-black/5 dark:hover:bg-white/10 transition-colors cursor-pointer focus:outline-none"
          >
            {copied ? (
              <Check size={14} className="text-emerald-500 dark:text-emerald-400" />
            ) : (
              <Copy size={14} />
            )}
          </button>
        </Tooltip>
      </div>

      <div className="overflow-x-auto rounded-xl border border-app-border shadow-md custom-scrollbar">
        <table ref={tableRef} className="w-full text-left text-sm border-collapse bg-app-table-bg [&_td]:align-top [&_th]:align-top">
          {children}
        </table>
      </div>
    </div>
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
    const sourcesMatch = msg.content.match(/<!-- SOURCES_DATA:\s*([\s\S]*?)\s*-->/);
    const citationMapMatch = msg.content.match(/<!-- CITATION_MAP:\s*([\s\S]*?)\s*-->/);

    let clean = msg.content;
    let parsedSources: AcademicCandidateSource[] = [];
    let parsedCitationMap: Record<string, string[]> = {};
    
    if (sourcesMatch) {
      clean = clean.replace(/<!-- SOURCES_DATA:[\s\S]*?-->/, "").trim();
      try {
        parsedSources = JSON.parse(sourcesMatch[1]);
      } catch (e) {
        console.error("Failed to parse sources data:", e);
      }
    }

    if (citationMapMatch) {
      clean = clean.replace(/<!-- CITATION_MAP:[\s\S]*?-->/, "").trim();
      try {
        // Robust JSON parse: strip markdown code fences, trailing commas
        let rawJson = citationMapMatch[1].trim();
        rawJson = rawJson.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
        rawJson = rawJson.replace(/,\s*([\]}])/g, "$1"); // trailing commas
        parsedCitationMap = JSON.parse(rawJson);
      } catch (e) {
        console.error("Failed to parse citation map data:", e);
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

    return { cleanContent: clean, sources: parsedSources, citationMap: parsedCitationMap };
  }, [msg.content]);

  const isDuplicateSource = useCallback((src: AcademicCandidateSource) => {
    if (!documents || documents.length === 0) return false;
    const normalize = (s: string) => s.replace(/\.pdf$/i, "").replace(/[^a-zA-Z0-9\s]/g, " ").toLowerCase().trim().replace(/\s+/g, " ");
    const srcNorm = normalize(src.title || "");
    if (!srcNorm) return false;
    const srcTokens = new Set(srcNorm.split(" "));

    for (const doc of documents) {
      const docNorm = normalize(doc.filename || "");
      if (!docNorm) continue;
      if (srcNorm === docNorm) return true;
      if (docNorm.length >= 20 && (srcNorm.startsWith(docNorm) || docNorm.startsWith(srcNorm))) return true;

      const docTokens = new Set(docNorm.split(" "));
      let intersection = 0;
      for (const t of srcTokens) {
        if (docTokens.has(t)) intersection++;
      }
      const minLen = Math.min(srcTokens.size, docTokens.size);
      if (minLen > 0 && intersection / minLen >= 0.75 && intersection >= 3) return true;
    }
    return false;
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
    const novelIndices = sources.map((s, i) => (!isDuplicateSource(s) ? i : -1)).filter(i => i !== -1);
    const areAllNovelSelected = novelIndices.length > 0 && novelIndices.every(i => isSourceChecked(sources[i], i));
    const nextState = !areAllNovelSelected;
    
    const updated = { ...userSelectionOverrides };
    novelIndices.forEach(i => {
      updated[i] = nextState;
    });
    setUserSelectionOverrides(updated);
  };

  const [importProgress, setImportProgress] = useState<{ current: number; total: number } | null>(null);

  const handleImport = async () => {
    const toImport = sources.filter((src, i) => !isDuplicateSource(src) && isSourceChecked(src, i));
    if (toImport.length === 0) return;

    setIsImporting(true);
    setImportProgress({ current: 0, total: toImport.length });

    // Register pending placeholder sources immediately in the sidebar so circular spinners appear
    const pendingItems = toImport.map((src, idx) => ({
      id: `pending-import-${Date.now()}-${idx}-${Math.random().toString(36).slice(2, 6)}`,
      filename: `${(src.title || src.doi || "Research Paper").trim()}.pdf`,
      type: "doi" as const,
      doi: src.doi,
      status: "uploading" as const,
    }));
    onAddPendingSources?.(pendingItems);

    try {
      let currentChatId = activeChatId;
      if (!currentChatId && onEnsureChatSession) {
        currentChatId = await onEnsureChatSession(toImport[0]?.title || "Research Paper");
      }
      if (!currentChatId) return;

      // Streamed batch ingestion via single HTTP request with real-time SSE progress
      const res = await fetch(`${backendUrl}/chats/${currentChatId}/import_sources_stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: toImport })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || `Server returned ${res.status}`);
      }

      await consumeSSEStream(res, (data: any) => {
        if (data.type === "progress") {
          const currentProgress = data.current || 0;
          setImportProgress({ current: currentProgress, total: toImport.length });
          if (data.doc) {
            onDocumentAdded?.(data.doc as DocType, currentChatId);
          }
          if (currentProgress > 0 && currentProgress <= pendingItems.length) {
            const pendingId = pendingItems[currentProgress - 1]?.id;
            if (pendingId !== undefined) {
              onResolvePendingSource?.(pendingId);
            }
          }
        } else if (data.type === "done") {
          setImportProgress({ current: toImport.length, total: toImport.length });
        }
      });

      setUserSelectionOverrides({});
    } catch (e) {
      console.error("Import sources failed:", e);
    } finally {
      // Ensure all pending source badges are cleaned up
      pendingItems.forEach(p => onResolvePendingSource?.(p.id));
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
          remarkPlugins={[remarkGfm]}
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
            ul: ({ node, ...props }: any) => <ul className="list-disc pl-6 my-2.5 space-y-1.5 text-app-text" {...props} />,
            ol: ({ node, ...props }: any) => <ol className="list-decimal pl-8 my-2.5 space-y-1.5 text-app-text" {...props} />,
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
            table: ({ children }: any) => <MarkdownTableBlock>{children}</MarkdownTableBlock>,
            thead: ({ children }: any) => (
              <thead className="bg-app-table-header text-app-text border-b border-app-border font-semibold select-none">
                {children}
              </thead>
            ),
            tbody: ({ children }: any) => (
              <tbody className="divide-y divide-app-divider">
                {children}
              </tbody>
            ),
            tr: ({ node, children, ...props }: any) => {
              const rowText = extractTableRowText(node, children);
              return (
                <TableRowContext.Provider value={rowText}>
                  <tr className="hover:bg-app-item-hover transition-colors align-top" {...props}>
                    {children}
                  </tr>
                </TableRowContext.Provider>
              );
            },
            th: ({ node, children, ...props }: any) => (
              <TableCellRenderer
                isHeader={true}
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
            td: ({ node, children, ...props }: any) => (
              <TableCellRenderer
                isHeader={false}
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
                <pre className="bg-app-code-bg p-3.5 rounded-xl overflow-x-auto text-xs text-app-text font-mono border border-app-border custom-scrollbar">
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
              <div className="px-4 py-2 bg-app-surface border-b border-app-divider flex items-center justify-between text-xs text-app-text-muted">
                <span className="text-app-text-muted">{t('chat.researchFound')}</span>
                {novelSourcesCount > 0 && (
                  <button 
                    onClick={(e) => { e.stopPropagation(); toggleSelectAll(); }}
                    className="hover:text-blue-600 font-medium cursor-pointer transition-colors text-blue-500"
                  >
                    {allNovelSelected ? "Deselect All" : "Select All"}
                  </button>
                )}
              </div>

              <div className="max-h-[360px] overflow-y-auto divide-y divide-app-divider p-1 custom-scrollbar">
                {sources.map((src, i) => {
                  const isAlreadyAdded = isDuplicateSource(src);
                  const isChecked = isAlreadyAdded || isSourceChecked(src, i);
                  return (
                    <div 
                      key={i} 
                      onClick={() => {
                        if (!isAlreadyAdded) {
                          setUserSelectionOverrides(prev => ({ ...prev, [i]: !isSourceChecked(src, i) }));
                        }
                      }}
                      className={`p-3 px-3.5 flex items-start justify-between gap-3 transition-colors rounded-xl m-1 ${
                        isAlreadyAdded 
                          ? "bg-emerald-500/[0.04] border border-emerald-500/10 cursor-default" 
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
                  onClick={handleImport}
                  disabled={isImporting || selectedCount === 0}
                  className="h-8 px-4 rounded-full bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed border-0 outline-none transition-colors"
                >
                  {isImporting ? (
                    <>
                      <Loader2 size={12} className="animate-spin" />
                      <span>
                        {importProgress ? `Adding ${importProgress.current}/${importProgress.total}...` : "Adding sources..."}
                      </span>
                    </>
                  ) : (
                    <>
                      <Plus size={13} />
                      <span>{t('chat.addToSources').replace('{count}', selectedCount > 0 ? `${selectedCount} ` : "")}</span>
                    </>
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
