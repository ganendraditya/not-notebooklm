import { describe, it, expect } from "vitest";
import { stripFileExtension, cleanDoi, normalizeTitle, isMatchingPaper, peekBibliographyTitles } from "@/lib/sourceUtils";

describe("sourceUtils (Non-Regex Academic Source Matching)", () => {
  it("strips common academic file extensions safely without regex", () => {
    expect(stripFileExtension("test.pdf")).toBe("test");
    expect(stripFileExtension("paper.final.txt")).toBe("paper.final");
    expect(stripFileExtension("report.docx")).toBe("report");
    expect(stripFileExtension("notes.md")).toBe("notes");
    expect(stripFileExtension("library.bib")).toBe("library");
    expect(stripFileExtension("export.ris")).toBe("export");
    expect(stripFileExtension("normal_text")).toBe("normal_text");
  });

  it("extracts titles from BibTeX file before uploading", async () => {
    const bibContent = `
@article{vaswani2017,
  author = {Ashish Vaswani},
  title = {Attention Is All You Need},
  year = {2017}
}
@inproceedings{devlin2019,
  author = {Jacob Devlin},
  title = {BERT: Pre-training of Deep Bidirectional Transformers},
  year = {2019}
}
`;
    const file = new File([bibContent], "collection.bib", { type: "application/x-bibtex" });
    const titles = await peekBibliographyTitles(file);
    expect(titles).toHaveLength(2);
    expect(titles[0]).toBe("Attention Is All You Need");
    expect(titles[1]).toBe("BERT: Pre-training of Deep Bidirectional Transformers");
  });

  it("extracts titles from RIS file before uploading", async () => {
    const risContent = `
TY  - JOUR
TI  - YOLOv4: Optimal Speed and Accuracy
AU  - Bochkovskiy, Alexey
PY  - 2020
ER  - 

TY  - CONF
TI  - Mask R-CNN
AU  - He, Kaiming
PY  - 2017
ER  - 
`;
    const file = new File([risContent], "cv.ris", { type: "application/x-research-info-systems" });
    const titles = await peekBibliographyTitles(file);
    expect(titles).toHaveLength(2);
    expect(titles[0]).toBe("YOLOv4: Optimal Speed and Accuracy");
    expect(titles[1]).toBe("Mask R-CNN");
  });

  it("returns empty array for non-bib/ris files", async () => {
    const file = new File(["binary pdf content"], "paper.pdf", { type: "application/pdf" });
    const titles = await peekBibliographyTitles(file);
    expect(titles).toEqual([]);
  });

  it("cleans and standardizes DOIs safely without regex", () => {
    expect(cleanDoi("https://doi.org/10.15100/0002003086")).toBe("10.15100/0002003086");
    expect(cleanDoi("http://doi.org/10.1016/j.jbusres.2020.08.028.")).toBe("10.1016/j.jbusres.2020.08.028");
    expect(cleanDoi("doi:10.1145/3313831.3376722;")).toBe("10.1145/3313831.3376722");
    expect(cleanDoi("10.1038/s41586-020-2649-2")).toBe("10.1038/s41586-020-2649-2");
  });

  it("preserves non-Latin scripts (Japanese, Chinese, Arabic) while normalizing", () => {
    const jpTitle = "術前CT画像情報と患者情報のAI解析による体外衝撃波結石破砕術の結果予測.txt";
    const normalized = normalizeTitle(jpTitle);
    expect(normalized).toBe("術前ct画像情報と患者情報のai解析による体外衝撃波結石破砕術の結果予測");
    expect(normalized).toContain("術前");
    expect(normalized).toContain("画像情報");
    expect(normalized).toContain("結果予測");
  });

  it("matches candidate paper against indexed document by exact DOI", () => {
    const candidate = {
      title: "Some Alternate Title",
      doi: "https://doi.org/10.15100/0002003086"
    };
    const existingDoc = {
      filename: "Local_File.pdf",
      title: "Local Title",
      doi: "10.15100/0002003086"
    };
    expect(isMatchingPaper(candidate, existingDoc)).toBe(true);
  });

  it("matches Japanese paper #2 by Title and filename when stored as .txt", () => {
    const candidate = {
      title: "術前CT画像情報と患者情報のAI解析による体外衝撃波結石破砕術の結果予測",
      doi: "https://doi.org/10.15100/0002003086"
    };
    const indexedDoc = {
      filename: "術前CT画像情報と患者情報のAI解析による体外衝撃波結石破砕術の結果予測.txt",
      title: "術前CT画像情報と患者情報のAI解析による体外衝撃波結石破砕術の結果予測",
      doi: "10.15100/0002003086"
    };
    expect(isMatchingPaper(candidate, indexedDoc)).toBe(true);
  });

  it("matches titles with brackets and slight punctuation differences", () => {
    const cand = {
      title: "Token 合併と後処理量子化に基づくVision Transformer推論高速化の実装と検証 [課題研究報告書]"
    };
    const existing = {
      filename: "Token 合併と後処理量子化に基づくVision Transformer推論高速化の実装と検証 [課題研究報告書].pdf"
    };
    expect(isMatchingPaper(cand, existing)).toBe(true);
  });
});
