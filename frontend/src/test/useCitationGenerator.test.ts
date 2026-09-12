import { describe, it, expect } from "vitest";
import { generateCitations } from "@/hooks/useCitationGenerator";

describe("useCitationGenerator (Academic Integrity & No Fake Fallbacks)", () => {
  it("formats fully verified journal paper accurately without hallucinations", () => {
    const citations = generateCitations(
      "Forecasting football match results in national league competitions using score-driven time series models",
      ["Siem Jan Koopman", "Rutger Lit"],
      "2019",
      "International Journal of Forecasting",
      "10.1016/j.ijforecast.2018.10.011",
      ""
    );

    // APA
    expect(citations.apa).toContain("Koopman, S. J., & Lit, R. (2019).");
    expect(citations.apa).toContain("International Journal of Forecasting.");
    expect(citations.apa).toContain("https://doi.org/10.1016/j.ijforecast.2018.10.011");
    expect(citations.apa).not.toContain("Anonymous");
    expect(citations.apa).not.toContain("Academic Publication");

    // IEEE
    expect(citations.ieee).toContain("S. J. Koopman and R. Lit");
    expect(citations.ieee).toContain("International Journal of Forecasting, 2019");

    // BibTeX
    expect(citations.bibtex).toContain("@article{");
    expect(citations.bibtex).toContain("journal = {International Journal of Forecasting}");
    expect(citations.bibtex).toContain("year = {2019}");
  });

  it("handles theses / skripsi with author and year but no journal cleanly", () => {
    const citations = generateCitations(
      "Improving Detection of Similarly Designed Retail Products With Size Variants",
      ["Ganendra Raditya Putra Satriawan"],
      "2026",
      "Uploaded Document",
      "",
      ""
    );

    expect(citations.apa).toBe("Satriawan, G. R. P. (2026). Improving Detection of Similarly Designed Retail Products With Size Variants.");
    expect(citations.apa).not.toContain("Academic Publication");
    expect(citations.apa).not.toContain("Anonymous");

    expect(citations.bibtex).toContain("@misc{");
    expect(citations.bibtex).not.toContain("journal = {Uploaded Document}");
    expect(citations.bibtex).not.toContain("journal = {Academic Publication}");
  });

  it("handles files without authors or year without fabricating 'Anonymous' or current year", () => {
    const citations = generateCitations(
      "applsci-10-00046-v2",
      [],
      "",
      "",
      "",
      ""
    );

    // APA rule: title moves to front, no date is (n.d.)
    expect(citations.apa).toBe("applsci-10-00046-v2. (n.d.).");
    expect(citations.apa).not.toContain("Anonymous");
    expect(citations.apa).not.toContain("2026");
    expect(citations.apa).not.toContain("Academic Publication");

    // IEEE
    expect(citations.ieee).toBe('"applsci-10-00046-v2," n.d.');

    // BibTeX
    expect(citations.bibtex).toContain("@misc{");
    expect(citations.bibtex).not.toContain("author =");
    expect(citations.bibtex).not.toContain("Anonymous");
  });
});
