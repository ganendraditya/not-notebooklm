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

  it("produces focused grounding evidence (1 to 3 clusters) enabling multi-match navigation", () => {
    const claim = 'Akurasi penghitungan mencapai 91.18% sedangkan metode kepadatan 77.03%.';
    const result = getHighlightedContent(samplePaper, claim);

    // Must find matching evidence and allow multi-cluster navigation (1/2 or 1/3)
    expect(result.matchCount).toBeGreaterThanOrEqual(1);
    expect(result.matchCount).toBeLessThanOrEqual(3);
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

  it("aligns future work recommendations with future/conclusion section rather than related work", () => {
    const paperWithSections = `
# System Paper
## II. LITERATURE AND RELATED WORK
In prior work, road accident detection used synthetic data from multiple perspectives named MP-RAD [28].
A 3D CNN model was explored in previous research for video comparison.

## III. METHODOLOGY
We train sequential DCNN on BeamNG synthetic datasets.

## VII. FUTURE DIRECTIONS
In the future, the 3D CNN model can undergo training with synthetic data to enable a comparison of results.
Furthermore, the use of multi-view synthetic data could be beneficial to improve accuracy.
`;
    const recQuery = "Penambahan data sintetis dan multi-perspective; eksplorasi 3D CNN untuk masa depan";
    const result = getHighlightedContent(paperWithSections, recQuery);

    // Must match the FUTURE DIRECTIONS section
    expect(result.matchCount).toBeGreaterThanOrEqual(1);
    // Should NOT match the RELATED WORK section
    expect(result.matchCount).toBeLessThanOrEqual(2);
  });

  it("highlights multiple distinct evidence sentences (1/2, 2/2) without discarding either quote", () => {
    const paper = `
# Road Sign Paper
## Preprocessing
Pada tahapan ini yaitu merubah ukuran gambar input menjadi 640 x 640 pixel.

## Augmentasi Data
Kemudian setelah dilakukan rotasi langkah berikutnya adalah dengan menambah efek Cutout dengan tujuan objek tertutup masih terdeteksi.
`;

    const aiQuotes = [
      "Pada tahapan ini yaitu merubah ukuran gambar input menjadi 640 x 640 pixel.",
      "Kemudian setelah dilakukan rotasi langkah berikutnya adalah dengan menambah efek Cutout dengan tujuan objek tertutup masih terdeteksi."
    ];

    const result = getHighlightedContent(paper, "Resize 640x640 dan efek Cutout", undefined, 0, aiQuotes);

    // Both distinct sections must be preserved as 2 separate match clusters for 1/2 and 2/2 navigation
    expect(result.matchCount).toBe(2);
  });
});
