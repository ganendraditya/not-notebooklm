export interface CitationFormats {
  apa: string;
  ieee: string;
  harvard: string;
  mla: string;
  chicago: string;
  bibtex: string;
  ris: string;
}

export const generateCitations = (
  title: string,
  authors: string[],
  year: string,
  journal: string,
  doi: string,
  url: string
): CitationFormats => {
  const cleanTitle = (title || "Untitled Document").replace(/\.$/, "").trim();
  const cleanYear = year && year !== "N/A" && year.trim().length > 0 ? year.trim() : "";
  const doiUrl = doi ? (doi.startsWith("http") ? doi : `https://doi.org/${doi}`) : url;

  // Filter out any generic placeholder journal names
  const genericJournals = new Set([
    "academic publication", "scholarly publication", "uploaded document", "journal", "peer-reviewed", ""
  ]);
  const hasJournal = Boolean(journal && !genericJournals.has(journal.trim().toLowerCase()));
  const cleanJournal = hasJournal ? journal.trim() : "";

  const validAuthors = Array.isArray(authors)
    ? authors.map(a => a.trim()).filter(a => a.length > 0 && a.toLowerCase() !== "anonymous")
    : [];
  const hasAuthors = validAuthors.length > 0;

  // Helper for authors formatted in APA / Harvard (Last, Initials)
  const formatApaAuthor = (a: string) => {
    const parts = a.split(/\s+/);
    if (parts.length === 1) return parts[0];
    const last = parts[parts.length - 1];
    const initials = parts.slice(0, -1).map(p => p[0] + ".").join(" ");
    return `${last}, ${initials}`;
  };

  const formatApaAuthorsList = (list: string[]) => {
    if (list.length === 0) return "";
    if (list.length === 1) return formatApaAuthor(list[0]);
    if (list.length === 2) return `${formatApaAuthor(list[0])}, & ${formatApaAuthor(list[1])}`;
    return `${list.slice(0, -1).map(formatApaAuthor).join(", ")}, & ${formatApaAuthor(list[list.length - 1])}`;
  };

  const apaAuthors = hasAuthors ? formatApaAuthorsList(validAuthors) : "";

  // Helper for IEEE authors (Initials Last)
  const formatIeeeAuthor = (a: string) => {
    const parts = a.split(/\s+/);
    if (parts.length === 1) return parts[0];
    const last = parts[parts.length - 1];
    const initials = parts.slice(0, -1).map(p => p[0] + ".").join(" ");
    return `${initials} ${last}`;
  };

  const ieeeAuthors = hasAuthors
    ? validAuthors.map(formatIeeeAuthor).join(" and ")
    : "";

  // Helper for MLA / Chicago authors
  const fullAuthors = validAuthors.join(", ");

  // 1. APA 7th Edition
  // Rule: If no author, title moves to the author position. If no year, use (n.d.).
  const apaYear = cleanYear ? `(${cleanYear})` : "(n.d.)";
  const apaJournalPart = cleanJournal ? ` ${cleanJournal}.` : "";
  const apaDoiPart = doiUrl ? ` ${doiUrl}` : "";
  const apa = hasAuthors
    ? `${apaAuthors} ${apaYear}. ${cleanTitle}.${apaJournalPart}${apaDoiPart}`
    : `${cleanTitle}. ${apaYear}.${apaJournalPart}${apaDoiPart}`;

  // 2. IEEE
  // Rule: If no author, start with quote title. If no year, use n.d.
  const ieeeJournalPart = cleanJournal ? ` ${cleanJournal},` : "";
  const ieeeYearPart = cleanYear ? ` ${cleanYear}.` : " n.d.";
  const ieeeDoiPart = doi ? ` doi: ${doi}.` : "";
  const ieee = hasAuthors
    ? `${ieeeAuthors}, "${cleanTitle},"${ieeeJournalPart}${ieeeYearPart}${ieeeDoiPart}`
    : `"${cleanTitle},"${ieeeJournalPart}${ieeeYearPart}${ieeeDoiPart}`;

  // 3. Harvard
  const harvardYear = cleanYear || "n.d.";
  const harvardJournalPart = cleanJournal ? ` ${cleanJournal}.` : "";
  const harvardUrlPart = doiUrl ? ` Available at: <${doiUrl}>.` : "";
  const harvard = hasAuthors
    ? `${apaAuthors}, ${harvardYear}. ${cleanTitle}.${harvardJournalPart}${harvardUrlPart}`
    : `${cleanTitle}, ${harvardYear}.${harvardJournalPart}${harvardUrlPart}`;

  // 4. MLA 9th Edition
  const mlaContainerParts: string[] = [];
  if (cleanJournal) mlaContainerParts.push(cleanJournal);
  if (cleanYear) mlaContainerParts.push(cleanYear);
  const mlaMiddle = mlaContainerParts.length > 0 ? ` ${mlaContainerParts.join(", ")}.` : "";
  const mlaDoiPart = doiUrl ? ` ${doiUrl}.` : "";
  const mla = hasAuthors
    ? `${fullAuthors}. "${cleanTitle}."${mlaMiddle}${mlaDoiPart}`
    : `"${cleanTitle}."${mlaMiddle}${mlaDoiPart}`;

  // 5. Chicago
  const chicagoYearPart = cleanYear ? ` (${cleanYear})` : " (n.d.)";
  const chicagoJournalPart = cleanJournal ? ` ${cleanJournal}` : "";
  const chicagoDoiPart = doiUrl ? ` ${doiUrl}.` : "";
  const chicago = hasAuthors
    ? `${fullAuthors}. "${cleanTitle}."${chicagoJournalPart}${chicagoYearPart}.${chicagoDoiPart}`
    : `"${cleanTitle}."${chicagoJournalPart}${chicagoYearPart}.${chicagoDoiPart}`;

  // 6. BibTeX
  const citeKeyPrefix = hasAuthors
    ? (validAuthors[0].split(/\s+/).pop() || "doc").toLowerCase().replace(/[^a-z0-9]/g, "")
    : (cleanTitle.split(/\s+/)[0] || "doc").toLowerCase().replace(/[^a-z0-9]/g, "");
  const citeKeyYear = cleanYear || "nd";
  const citeKeyTitle = (cleanTitle.split(/\s+/)[1] || "ref").toLowerCase().replace(/[^a-z0-9]/g, "");
  const citeKey = `${citeKeyPrefix}${citeKeyYear}${citeKeyTitle}`;

  const entryType = cleanJournal ? "article" : "misc";
  const bibtexFields: string[] = [
    `  title = {${cleanTitle}}`,
  ];
  if (hasAuthors) {
    bibtexFields.push(`  author = {${validAuthors.join(" and ")}}`);
  }
  if (cleanJournal) {
    bibtexFields.push(`  journal = {${cleanJournal}}`);
  }
  if (cleanYear) {
    bibtexFields.push(`  year = {${cleanYear}}`);
  }
  if (doi) {
    bibtexFields.push(`  doi = {${doi}}`);
  }
  if (doiUrl) {
    bibtexFields.push(`  url = {${doiUrl}}`);
  }
  const bibtex = `@${entryType}{${citeKey},\n${bibtexFields.join(",\n")}\n}`;

  // 7. RIS
  const risLines: string[] = [
    `TY  - ${cleanJournal ? "JOUR" : "GEN"}`,
    `TI  - ${cleanTitle}`,
  ];
  if (hasAuthors) {
    validAuthors.forEach(a => risLines.push(`AU  - ${a}`));
  }
  if (cleanJournal) {
    risLines.push(`JO  - ${cleanJournal}`);
  }
  if (cleanYear) {
    risLines.push(`PY  - ${cleanYear}`);
  }
  if (doi) {
    risLines.push(`DO  - ${doi}`);
  }
  if (doiUrl) {
    risLines.push(`UR  - ${doiUrl}`);
  }
  risLines.push("ER  -");
  const ris = risLines.join("\n");

  return { apa, ieee, harvard, mla, chicago, bibtex, ris };
};