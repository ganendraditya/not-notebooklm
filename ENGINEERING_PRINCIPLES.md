# NotbookLM Engineering Manifesto

Dokumen ini adalah kontrak arsitektur dan pedoman utama untuk seluruh proses *development*, pemeliharaan, dan *refactoring* di dalam codebase NotbookLM. Setiap baris kode yang ditulis atau diubah **WAJIB** tunduk pada 3 prinsip fundamental berikut:

## 1. DRY (Don't Repeat Yourself) & Single Source of Truth
DRY bukan sekadar "jangan *copy-paste* kode yang bentuknya mirip". DRY adalah tentang **Efisiensi Logika Bisnis**. Banyak orang terjebak menyatukan kode yang kebetulan sama secara teks (*coincidental duplication*), padahal tujuan domainnya berbeda, yang justru berakibat fatal di kemudian hari.

Kutipan asli DRY: *"Every piece of knowledge must have a single, unambiguous, authoritative representation within a system."* Kuncinya adalah **Knowledge (Logika Bisnis)**, bukan kemiripan sintaks kode.

**Railguards & Definisi Objektif DRY:**
- **DUPLIKASI LOGIKA (Wajib DRY):** Jika ada satu aturan bisnis yang berubah (contoh: PPN naik jadi 12%, atau cara memvalidasi ekstensi `.pdf` berubah) dan Anda harus mencari & mengubahnya di 3 file berbeda, itu melanggar DRY.
  - *Solusi:* Buat 1 *Single Source of Truth* (misal fungsi `validate_pdf_extension()` atau fungsi `calculate_tax()`) yang dipanggil oleh semua modul.
- **DUPLIKASI KEBETULAN (DILARANG DRY):** Jika Fungsi A (kalkulasi diskon keranjang) dan Fungsi B (kalkulasi pajak bea cukai impor) kebetulan memiliki rumus *sama persis* (yakni `x * y`) saat ini, **jangan pernah disatukan**. Keduanya mewakili *domain bisnis/aktor* yang berbeda. Jika besok pajak impor ditambah biaya admin flat, perubahan tersebut tidak boleh merusak kalkulasi diskon keranjang.
  - *Aturan Emas:* *"Duplication is far cheaper than the wrong abstraction."* Biarkan *WET (Write Everything Twice)* sampai pola perubahan logikanya benar-benar jelas. Jika mereka diubah oleh alasan yang berbeda (satu oleh Marketing, satu oleh tim Legal), **pisahkan**.

- **Aturan Implementasi:** Hindari *magic numbers* yang tersebar di banyak file. Gunakan layer `services/` atau konstanta global sebagai *Single Source of Truth* untuk logika aplikasi yang memang mempresentasikan "Satu Pengetahuan". Router dan UI hanya bertugas memanggil dan merender.

## 2. Orthogonality (Decoupled & Separation of Concerns)
Komponen sistem harus berdiri sendiri (independen) dan tidak tumpang tindih. *Butterfly effect* (ngubah fitur A, fitur C ikut rusak) adalah tanda *coupling* yang buruk.

**Definisi Objektif Ortogonalitas (Bukan Sekadar Jumlah Baris):**
Ortogonalitas **TIDAK** ditentukan oleh jumlah baris (*Lines of Code* / LOC). Sebuah file 1000 baris yang berisi satu kesatuan rumus algoritma murni tetap ortogonal jika ia independen. Jumlah baris yang panjang hanyalah *"First Stage Filter"* (indikator awal) untuk mengecek apakah sebuah komponen memikul terlalu banyak beban.

Standar objektif untuk mengukur Ortogonalitas dalam proyek ini:
1. **The Testability Test:** Jika sebuah modul (UI/Fungsi) dapat diuji (*Unit Test*) secara mandiri dengan input/output tanpa perlu menyalakan database, web-socket, atau merakit mock sistem lain yang kompleks, maka ia ortogonal.
2. **The Side-Effect Test:** Jika Anda mengubah warna tombol di UI atau mengganti pustaka *database*, dan Anda TIDAK perlu menyentuh file *business logic*, maka sistem tersebut ortogonal.
3. **High Cohesion & Low Coupling:** File harus memiliki fokus tugas yang sangat padat (*High Cohesion*) dan ketergantungan yang minimal terhadap file lain (*Low Coupling*). Hindari "God Object" (komponen/file yang mencampur urusan rendering UI, HTTP Request, dan manipulasi data sekaligus).

- **Aturan:** Modul UI tidak boleh mengurus *fetching* HTTP mentah. Router API tidak boleh mengurus pembacaan *byte file* di disk.
- **Implementasi:** 
  - Terapkan **Controller-Service Pattern** di Backend. 
  - Terapkan **Atomic Components & Custom Hooks** di Frontend (pisahkan UI rendering dari state management & side-effects).
  - Jika terjadi bug pada pencarian OpenAlex, sistem pembacaan PDF lokal tidak boleh ikut *crash*.

## 3. Reversibility (Fleksibilitas & Swap-ability)
Keputusan teknologi (Tech Stack) bersifat dinamis dan bisa berubah kapan saja sesuai kebutuhan bisnis (misal: pindah dari SQLite ke PostgreSQL, pindah dari Qdrant ke Pinecone/Milvus, pindah dari Gemini ke Claude).
- **Aturan:** Kode harus **MUDAH DIUBAH**. Perubahan infrastruktur *third-party* tidak boleh memaksa kita melakukan *rewrite* pada logika inti aplikasi.
- **Implementasi:**
  - Gunakan **Abstraksi (Interface/Port)**. Komponen utama aplikasi tidak boleh peduli *database* apa yang dipakai.
  - Hindari penamaan spesifik *vendor* pada fungsi logic (Contoh buruk: `delete_qdrant_vectors()`. Contoh baik: `vector_store.delete_document_vectors()`).
  - ORM (seperti SQLAlchemy) harus menangani dialek *database*, jangan pernah membocorkan *raw SQL query* yang spesifik vendor (seperti fungsi bawaan sqlite3) ke dalam layer bisnis.

---
*Dibuat sebagai komitmen arsitektural. Jika refactoring melanggar salah satu dari prinsip ini, maka refactoring tersebut dianggap gagal.*