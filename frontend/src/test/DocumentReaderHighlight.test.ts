import { describe, it, expect } from "vitest";
import { getHighlightedContent } from "../components/RightSidebar/DocumentReaderUtils";

describe("DocumentReaderUtils Highlighting & Focus Grounding", () => {
  const samplePaper = `
Jurnal Riset Transportasi, Vol. 5, No. 2, Agustus 2020, hlm. 100-110.
p-ISSN: 2302-2949, e-ISSN: 2407-7267.

# SISTEM PENGATUR LALU LINTAS CERDAS BERBASIS VISI KOMPUTER

Abstrak — Lalu lintas perkotaan semakin padat sehingga diperlukan sistem pemantauan otomatis.
Penelitian ini membandingkan metode panjang antrean dengan kepadatan piksel.
Pengujian sistem kendali sinyal dengan metode panjang antrean menghasilkan akurasi hingga 91.18% sedangkan metode kepadatan luas piksel mencapai 77.03%.

1. Pendahuluan
Sistem transportasi cerdas (ITS) memanfaatkan kamera CCTV untuk memantau arus kendaraan di persimpangan jalan.
Kamera menangkap video lalu lintas dan meneruskannya ke sistem pengolahan citra digital.

2. Metodologi Penelitian
Pengolahan citra dilakukan dengan background subtraction dan blob detection.
Threshold yang digunakan sebesar 100 dengan kernel 3x3 untuk mereduksi noise pada citra.

3. Hasil dan Pembahasan
Dari hasil pengujian sebanyak 10 kali percobaan pada video CCTV durasi 120 detik, metode panjang antrean mencapai akurasi 91.18% pada pagi hari.
Pada malam hari, akurasi mengalami penurunan menjadi 73% akibat pendaran lampu kendaraan.

4. Kesimpulan
Metode panjang antrean terbukti lebih presisi dibandingkan metode luas piksel untuk penentuan durasi lampu hijau.
`;

  it("produces laser-focused grounding (<= 2 clusters) on empirical metric claims", () => {
    const claim = 'Akurasi penghitungan mencapai 91.18% sedangkan metode kepadatan 77.03%.';
    const result = getHighlightedContent(samplePaper, claim);

    // Must find matching evidence
    expect(result.matchCount).toBeGreaterThanOrEqual(1);
    // Must NEVER produce dozens of clusters across the document
    expect(result.matchCount).toBeLessThanOrEqual(2);
  });

  it("does not falsely highlight header publication years (e.g. 2020) on author queries", () => {
    const authorQuery = "Cahyono & Budiyanto (2020)";
    const result = getHighlightedContent(samplePaper, authorQuery);

    // An author query should not highlight the journal header "Agustus 2020, hlm."
    expect(result.matchCount).toBe(0);
  });

  it("rejects conversational fluff / generic queries with low significance (< 20 points)", () => {
    const vagueQuery = "Penelitian ini menggunakan sistem lalu lintas pada jalan.";
    const result = getHighlightedContent(samplePaper, vagueQuery);

    // Vague queries with only common stopwords/words should yield 0 highlights rather than cluttering the document
    expect(result.matchCount).toBe(0);
  });
});
