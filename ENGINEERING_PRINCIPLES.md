# NotbookLM Engineering Manifesto

Dokumen ini adalah kontrak arsitektur dan pedoman utama untuk seluruh proses *development*, pemeliharaan, dan *refactoring* di dalam codebase NotbookLM. Setiap baris kode yang ditulis atau diubah **WAJIB** tunduk pada 3 prinsip fundamental berikut:

## 1. DRY (Don't Repeat Yourself) & Single Source of Truth
DRY bukan sekadar "jangan *copy-paste* kode yang bentuknya mirip". DRY adalah tentang **Efisiensi Logika Bisnis**.
- **Aturan:** Jika sebuah *business rule* (contoh: cara memvalidasi PDF, cara menghitung skor relevansi, aturan penulisan sitasi) berubah, kita **hanya perlu mengubahnya di SATU tempat**.
- **Implementasi:** Hindari *magic numbers* yang tersebar di banyak file. Gunakan layer `services/` sebagai *Single Source of Truth* untuk logika aplikasi. Router dan UI hanya bertugas memanggil dan merender.

## 2. Orthogonality (Decoupled & Separation of Concerns)
Komponen sistem harus berdiri sendiri (independen) dan tidak tumpang tindih. *Butterfly effect* (ngubah fitur A, fitur C ikut rusak) adalah tanda *coupling* yang buruk.
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