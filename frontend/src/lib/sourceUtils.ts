const PUNCTUATION_SET = new Set([
  "!", "\"", "#", "$", "%", "&", "'", "(", ")", "*", "+", ",", "-", ".", "/",
  ":", ";", "<", "=", ">", "?", "@", "[", "\\", "]", "^", "_", "`", "{", "|", "}", "~",
  "・", "、", "。", "「", "」", "『", "』", "【", "】", "（", "）", "〔", "〕", "〈", "〉", "《", "》",
  "‘", "’", "“", "”", "—", "–", "…", "·", "¡", "¿", "«", "»", "―"
]);

export function stripFileExtension(filename?: string): string {
  if (!filename) return "";
  const trimmed = filename.trim();
  const lastDot = trimmed.lastIndexOf(".");
  if (lastDot > 0) {
    const ext = trimmed.slice(lastDot).toLowerCase();
    if (ext === ".pdf" || ext === ".txt" || ext === ".docx" || ext === ".doc" || ext === ".md") {
      return trimmed.slice(0, lastDot).trim();
    }
  }
  return trimmed;
}

export function cleanDoi(rawDoi?: string): string {
  if (!rawDoi) return "";
  let doi = rawDoi.trim().toLowerCase();
  const prefixes = [
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "dx.doi.org/",
    "doi:"
  ];
  for (const p of prefixes) {
    if (doi.startsWith(p)) {
      doi = doi.slice(p.length);
      break;
    }
  }
  while (doi.endsWith(".") || doi.endsWith("/") || doi.endsWith(";") || doi.endsWith(")")) {
    doi = doi.slice(0, -1);
  }
  return doi.trim();
}

export function normalizeTitle(text?: string): string {
  if (!text) return "";
  const stripped = stripFileExtension(text.trim());
  const normalized = stripped.normalize("NFKC").toLowerCase();
  const chars = Array.from(normalized);
  const result: string[] = [];
  for (const ch of chars) {
    if (PUNCTUATION_SET.has(ch)) {
      result.push(" ");
    } else {
      result.push(ch);
    }
  }
  return result.join("").split(" ").filter(Boolean).join(" ");
}

export function isMatchingPaper(
  candidate: { title?: string; filename?: string; doi?: string; url?: string },
  target: { title?: string; filename?: string; doi?: string; url?: string }
): boolean {
  // 1. DOI Matching (100% exact and definitive)
  const candDoi = cleanDoi(candidate.doi);
  const targetDoi = cleanDoi(target.doi);
  if (candDoi && targetDoi && candDoi === targetDoi) {
    return true;
  }

  // 2. URL Matching
  if (candidate.url && target.url && candidate.url.trim() === target.url.trim()) {
    return true;
  }

  // 3. Title Matching (Unicode-safe, no regex)
  const candNorm = normalizeTitle(candidate.title || candidate.filename);
  if (!candNorm) return false;

  const compareTarget = (tNorm: string): boolean => {
    if (!tNorm) return false;
    if (candNorm === tNorm) return true;
    if (candNorm.length >= 15 && (candNorm.startsWith(tNorm) || tNorm.startsWith(candNorm))) return true;

    // Token overlap comparison
    const cTokens = new Set(candNorm.split(" "));
    const tTokens = new Set(tNorm.split(" "));
    let intersection = 0;
    for (const token of cTokens) {
      if (tTokens.has(token)) intersection++;
    }
    const minTokens = Math.min(cTokens.size, tTokens.size);
    if (minTokens >= 3 && intersection / minTokens >= 0.75) return true;

    return false;
  };

  const targetTitleNorm = normalizeTitle(target.title);
  const targetFilenameNorm = normalizeTitle(target.filename);

  return compareTarget(targetTitleNorm) || compareTarget(targetFilenameNorm);
}
