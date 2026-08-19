# Frontier AI Chatbot UI/UX Design System Guidelines

Aturan standar desain UI/UX untuk NotbookLM yang mengadopsi standar sistem desain produk AI frontier (seperti ChatGPT, Claude, NotebookLM, dan Gemini).

---

## 1. Spatial System (8-Point / 4-Point Grid)
Semua padding, margin, gap, dan ukuran dimensi harus mengikuti kelipatan **4px** dan **8px**:

* **Micro Spacing (4px - 8px):**
  * `4px` (`gap-1`, `p-1`, `m-1`): Jarak mikro antar ikon dan teks pendukung, margin halus.
  * `8px` (`gap-2`, `p-2`, `py-1.5 px-2`): Jarak antar elemen tombol, badge, checkbox, dan list item rapat.
* **Component Spacing (12px - 16px):**
  * `12px` (`gap-3`, `p-3`, `space-y-3`): Padding kartu informasi, container dropdown, dan modal pop-up.
  * `16px` (`gap-4`, `p-4`, `px-4 py-2.5`): Padding chat bubble pengguna, padding header panel, dan wrapper section.
* **Macro & Layout Spacing (24px - 48px):**
  * `24px` (`p-6`, `space-y-6`): Jarak vertikal antar giliran chat (*chat turns*).
  * `32px` - `48px` (`pt-10 sm:pt-12`, `pb-8`): Margin bernapas atas/bawah pada kanvas chat utama.

---

## 2. Typography Scale & Line-Heights
Fokus utama adalah **keterbacaan teks panjang (*long-form readability*)** dengan base bodytext **16px** dan line-height yang longgar (1.6 - 1.65):

| Elemen | Ukuran Font | Tailwind Class | Penggunaan |
| :--- | :--- | :--- | :--- |
| **Display / Hero** | `32px - 36px` | `text-3xl font-bold tracking-tight` | Layar sambutan awal (*empty hero state*). |
| **Heading H1** | `24px` | `text-2xl font-bold tracking-tight` | Judul bab utama di markdown AI. |
| **Heading H2** | `20px` | `text-xl font-bold tracking-tight` | Sub-bab di markdown AI. |
| **Heading H3** | `18px` | `text-lg font-semibold` | Sub-section / judul grup kecil. |
| **Body Text (Base)** | `16px` | `text-[16px] leading-[1.65] break-words` | Teks utama prompt pengguna, jawaban AI, dan textarea input. |
| **Subhead & UI Label** | `13px - 14px` | `text-sm font-medium`, `text-[13px]` | Label tombol utama, navigasi breadcrumb, judul paper. |
| **Caption & Small** | `12px` | `text-xs text-gray-400 leading-normal` | Subtitle status, disclaimer di bawah kolom input, tanggal. |
| **Micro Badge & Mono** | `10px - 11px` | `text-[10px]`, `text-[11px] font-mono` | Badge PDF, counter sources, pill hitungan. |

---

## 3. Grid System & Container Constraints

* **Single-Column Centered Chat Layout:**
  * Area chat dibatasi maksimal `max-w-3xl` (**768px**).
  * Mencegah baris teks terlalu panjang ke samping agar mata tidak cepat lelah saat membaca (*optimal 65-80 characters per line*).
  * Terpusat di tengah dengan `mx-auto`.
* **Sidebar Dimensions:**
  * **Left Sidebar (Chat History):** Lebar tetap `w-[260px]` untuk ergonomi navigasi satu tangan.
  * **Right Sidebar (Sources & Discovery):** Lebar `w-80` (**320px**) hingga `w-96` (**384px**) saat mode pencarian melebar.

---

## 4. Container & Visual Aesthetics

* **Color & Contrast Hierarchy:**
  * Background Utama: `#212121`
  * Left Sidebar: `#171717` (lebih gelap untuk hierarki kedalaman)
  * Right Sidebar / Cards: `#1e1f20` & `#28292c`
  * Chat Bubble Pengguna: `#2f2f2f` dengan teks putih kontras tinggi
* **Border Radii:**
  * Input Bar & Hero Cards: `rounded-2xl` hingga `rounded-3xl` (memberi kesan modern & ramah).
  * Action Buttons & Dropdown: `rounded-xl` atau `rounded-lg`.
  * Pills / Counter Badges: `rounded-full`.
* **Action Buttons & Alignment:**
  * Ikon berukuran `16px` dengan area sentuh `p-1.5 rounded-lg`.
  * **Pesan Pengguna:** Tombol aksi (Copy & Edit) harus selalu **rata kanan (*flush right*)** sejajar lurus dengan tepi kanan balon chat.
  * **Jawaban AI:** Tombol aksi (Copy) harus selalu **rata kiri (*flush left*)** sejajar lurus dengan huruf pertama teks jawaban.

---

## 5. Language & UI Copy Standard (Strict 100% English for System UI)

Semua elemen antarmuka sistem (UI chrome, placeholders, buttons, tooltips, modal, alert badges, pills, dan empty states) **HARUS 100% KONSISTEN MENGGUNAKAN BAHASA INGGRIS**:

* **Placeholders:**
  * `Ask NotbookLM anything`
  * `Ask a question about this source...` (When focused on a document)
  * `Type your next message (automatically queued)...`
* **Focused Source Pills & Badges:**
  * `Focused on: [Title]` with `[Cancel]` button.
  * Chat bubble tag: `Focus: [Title]`.
* **Abstract & Indexation Badges:**
  * `ABSTRACT` with `✓ Official Abstract`.
  * `AI Synthesis Overview` with `Paywalled Source`.
  * `AI Overview Note: Original abstract is protected behind publisher paywall...`
* **Sources & Actions:**
  * `Ask`, `Cite`, `Copy Link`, `Download`, `Select All`, `Deselect All`, `Import Sources`.
* **System Footers & Loading:**
  * `Searching sources & generating response...`
  * `NotbookLM can make mistakes. Verify important info.`
  * `Queued Messages` - `Sends after agent finishes working`.

*(Catatan: Bahasa respon percakapan AI tetap adaptif mengikuti bahasa pengguna, namun seluruh UI, teks kontrol, dan label sistem harus selalu 100% Bahasa Inggris baku).*
