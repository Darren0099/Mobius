# Mobius — Offline Desktop Assistant & File Studio

**Mobius** adalah aplikasi Windows 10/11 bergaya *dynamic island* di tengah atas layar: bar dengan mata animasi, drag-and-drop alat konversi file, dan asisten komputer melalui perintah teks atau suara Bahasa Indonesia.

**Tidak ada server, API key, akun, maupun telemetri.** File dan rekaman suara diproses secara lokal. Pencarian lewat browser tentu membutuhkan internet untuk menampilkan hasil Google. Instalasi pertama dependensi dan model suara juga membutuhkan internet **sekali saja**.

## Desain

- Warna utama `#C7FF10` (electric lime), sekunder `#83AF3B`, black `#141414`, off-white `#F5F5F8`, warm white `#FBF8EF` — mengacu pada referensi desain.
- Font Urbanist dipilih bila sudah tersedia di Windows, dengan fallback Segoe UI. Font **tidak** disertakan dalam paket.
- Bar selalu di atas di tengah atas monitor; berkedip dan mengikuti kursor; melebar saat diseret file atau diklik.
- Dua tab: **File Studio** dan **Mobius Assistant**.

## Perintah yang didukung

| Ucapkan atau ketik | Hasil |
| --- | --- |
| `Mobius buka notepad dan kalkulator` | Jalankan beberapa aplikasi Windows **dari daftar yang diizinkan** |
| `Mobius buka browser dan cari tutorial Python` | Buka pencarian browser default (perlu internet) |
| `Mobius ubah PDF laporan menjadi img` | Cari `laporan.pdf` di Desktop/Documents/Downloads atau drop file; simpan gambar ke folder output |
| `Mobius ubah Word laporan menjadi PDF` | Konversi Word secara lokal |
| `Mobius matikan laptop dalam waktu 10 menit lagi` | Tampilkan **konfirmasi** sebelum menjadwalkan shutdown 600 detik |
| `Mobius batalkan shutdown` | Batalkan jadwal shutdown |
| `Mobius putar musik acak` | Putar file audio acak dari folder Windows Music melalui pemutar default |

Assistant menggunakan *intent parser* yang berjalan lokal, **bukan AI percakapan generatif atau pengontrol komputer yang menguasai semua aplikasi**. Perintah yang belum dikenali akan diberi penjelasan; teks dari mikrofon **tidak** pernah dieksekusi sebagai kode shell. Pencarian nama file terbatas pada folder user standar tanpa pemindaian seluruh drive.

**Aplikasi yang bisa dibuka:** Notepad, Calculator, Explorer, Paint, Terminal, Command Prompt, VS Code, Chrome, Edge, Firefox, Spotify, Discord (apabila terpasang dan command tersedia). Tambahkan alias terpercaya di `mobius/assistant_core.py` agar aplikasi lain dikenali.

## Sembilan alat konversi file

| Alat | Catatan |
| --- | --- |
| Gambar → PDF | Gabungkan banyak gambar ke satu PDF |
| PDF → Gambar | Ekspor per halaman JPG/PNG/WEBP |
| Word → PDF | Mengutamakan MS Word / LibreOffice jika terpasang |
| PDF → Word | Mengutamakan pdf2docx jika terpasang, fallback ekstraksi teks |
| Gabung PDF | Minimal 2 PDF |
| Pisah PDF | Satu PDF per halaman |
| Kompres PDF | Optimasi lossless, tidak selalu menjadi lebih kecil |
| Putar PDF | Rotasi 90° |
| Ubah Format Gambar | PNG, JPG, WEBP |

Folder hasil default `Documents\Mobius`. Hasil tidak menimpa nama file yang sudah ada. **PDF hasil scan belum memiliki OCR**, dan layout PDF→Word kompleks mungkin tidak identik.

## Instalasi Windows

1. Pastikan Python **3.12** atau **3.11** terpasang, termasuk `py` launcher.
2. Ekstrak folder sumber dan klik dua kali **`run-windows.bat`**. Pertama kali akan menginstal pustaka Python secara lokal. Setelah itu aplikasi bisa dijalankan tanpa koneksi.
3. Klik bar Mobius untuk membuka dua tab, atau seret gambar/PDF/DOCX dari File Explorer ke bar untuk langsung masuk File Studio.
4. Untuk **perintah suara**: jalankan **`install-voice-windows.bat`** **sekali saat terkoneksi internet**. Script menginstal faster-whisper dan mengunduh model multilingual `Systran/faster-whisper-base` ke `~\.mobius\models`. Setelah unduhan selesai, proses STT tidak memakai internet.
5. Pada tab Assistant, pilih **Bicara (7s)** untuk satu instruksi, atau **Hands-free ON** untuk mengaktifkan mikrofon terus-menerus sampai kamu mematikannya. Awali perintah dengan **"Mobius"**. Pada Hands-free, deteksi ucapan dan transkripsi berjalan di laptop, dapat memakai CPU cukup besar; hasil pengenalan bisa salah dalam situasi bising.
6. Untuk membuat **Mobius.exe** sendiri jalankan **`build-windows.bat`** di Windows. Proses build memasukkan library suara, tetapi **model** tetap harus disiapkan satu kali dengan langkah (4).

**Build EXE di GitHub:** Buka tab **Actions** → pilih **Build Mobius Windows EXE** → Run workflow → unduh artifact `Mobius-Windows-exe`. Windows EXE dapat dijalankan tanpa instalasi Python terpisah; voice setup memerlukan model serta pustaka runtime yang telah dibundel.

Klik kanan ikon tray untuk membuka Mobius, membuka folder hasil, mengaktifkan startup saat login Windows, atau keluar.

## Keselamatan dan privasi

- Hands-free **OFF secara default**; izin mikrofon diperlukan dari Windows. Audio tidak disimpan, dikirim, atau diproses di cloud.
- Perintah shutdown memerlukan persetujuan Yes/No dengan opsi **No** sebagai default. Gunakan `Mobius batalkan shutdown` jika sudah dijadwalkan.
- Aplikasi hanya dapat menjalankan nama aplikasi dari daftar yang diketahui; tidak menjalankan teks acak melalui `cmd` atau PowerShell.
- Google Search membuka URL di browser: Mobius sendiri offline, tetapi halaman hasil membutuhkan internet.
- Musik dimainkan dari file yang tersimpan secara lokal; tidak otomatis streaming Spotify/YouTube.
- Model `faster-whisper-base` memakai CPU di Windows; bukan asisten LLM serbaguna. Hands-free bergantung pada kemampuan laptop dan noise lingkungan.
- Fullscreen eksklusif bisa menutupi bar selalu-di-atas.

## Struktur

```text
Mobius/
├─ app.py
├─ assets/                  # ikon Mobius
├─ mobius/
│  ├─ ui.py                 # dynamic island, tabs, mic, drag/drop
│  ├─ engine.py             # offline file conversion
│  ├─ assistant_core.py     # parser perintah dan tindakan aman
│  └─ voice.py              # faster-whisper offline + opt-in hands-free
├─ scripts/download_voice.py
├─ tests/                   # tes engine dan assistant
├─ requirements*.txt
├─ run-windows.bat
├─ install-voice-windows.bat
├─ build-windows.bat
└─ .github/workflows/windows-exe.yml
```

### Menjalankan tes

```powershell
python -m pip install -r requirements.txt pytest
python -m pytest -q tests
```

## Pengembangan selanjutnya

Kalau ingin kemampuan AI yang lebih luas: integrasikan LLM **lokal** (misal via Ollama) di belakang *permission broker* yang meminta izin sebelum tindakan berbahaya. Arsitektur ini sengaja membatasi eksekusi langsung demi keamanan, terutama pada input mikrofon yang mungkin salah mengenali perintah.
