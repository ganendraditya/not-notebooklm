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
  const cleanTitle = title.replace(/\.$/, "").trim();
  const cleanYear = year || "2024";
  const cleanJournal = journal || "Academic Publication";
  const doiUrl = doi ? (doi.startsWith("http") ? doi : `https://doi.org/${doi}`) : url;
  const authorList = authors.length > 0 ? authors : ["Anonymous"];
  
  // APA 7th
  const apaAuthors = authorList.map(a => {
    const parts = a.trim().split(" ");
    if (parts.length === 1) return parts[0];
    const last = parts[parts.length - 1];
    const initials = parts.slice(0, -1).map(p => p[0] + ".").join(" ");
    return `${last}, ${initials}`;
  }).join(", ");
  const apa = `${apaAuthors} (${cleanYear}). ${cleanTitle}. ${cleanJournal}.${doiUrl ? ` ${doiUrl}` : ""}`;

  // IEEE
  const ieeeAuthors = authorList.map(a => {
    const parts = a.trim().split(" ");
    if (parts.length === 1) return parts[0];
    const last = parts[parts.length - 1];
    const initials = parts.slice(0, -1).map(p => p[0] + ".").join(" ");
    return `${initials} ${last}`;
  }).join(" and ");
  const ieee = `${ieeeAuthors}, "${cleanTitle}," ${cleanJournal}, ${cleanYear}.${doi ? ` doi: ${doi}.` : ""}`;

  // Harvard
  const harvard = `${apaAuthors}, ${cleanYear}. ${cleanTitle}. ${cleanJournal}.${doiUrl ? ` Available at: <${doiUrl}>.` : ""}`;

  // MLA 9th
  const mlaAuthors = authorList.join(", ");
  const mla = `${mlaAuthors}. "${cleanTitle}." ${cleanJournal}, ${cleanYear}.${doiUrl ? ` ${doiUrl}.` : ""}`;

  // Chicago
  const chicago = `${mlaAuthors}. "${cleanTitle}." ${cleanJournal} (${cleanYear}).${doiUrl ? ` ${doiUrl}.` : ""}`;

  // BibTeX
  const citeKey = (authorList[0].split(" ").pop() || "paper").toLowerCase().replace(/[^a-z0-9]/g, "") + cleanYear + (cleanTitle.split(" ")[0] || "study").toLowerCase().replace(/[^a-z0-9]/g, "");
  const bibtex = `@article{${citeKey},
  title = {${cleanTitle}},
  author = {${authorList.join(" and ")}},
  journal = {${cleanJournal}},
  year = {${cleanYear}}${doi ? `,\n  doi = {${doi}}` : ""}${doiUrl ? `,\n  url = {${doiUrl}}` : ""}
}`;

  // RIS
  const ris = `TY  - JOUR
TI  - ${cleanTitle}
${authorList.map(a => `AU  - ${a}`).join("\n")}
JO  - ${cleanJournal}
PY  - ${cleanYear}
${doi ? `DO  - ${doi}\n` : ""}${doiUrl ? `UR  - ${doiUrl}\n` : ""}ER  -`;

  return { apa, ieee, harvard, mla, chicago, bibtex, ris };
};