# MOBIUS v0.3 · Ambient Offline Assistant + File Studio

**Mobius** adalah asisten Windows 10/11 yang mendengarkan perintah setelah startup dan menyatukan konversi dokumen serta asisten suara dalam **satu layar**. Bar kecil berwarna lime hanya terlihat saat desktop kosong/aktif. Saat browser atau aplikasi lain sedang aktif, bar disembunyikan, tetapi pendengar suara tetap berjalan. Tidak ada layanan cloud yang menerima rekaman suara atau file.

## Instalasi dari GitHub (Windows PowerShell)

```powershell
cd "$HOME\Documents"
git clone https://github.com/Darren0099/Mobius.git
cd .\Mobius
.\run-windows.bat
```

> Jika sebelumnya folder Mobius diambil dari ZIP, folder tersebut **bukan Git repository**, sehingga `git pull` tidak akan berfungsi. `git clone` dulu ke folder baru atau ikuti langkah konversi ZIP di bawah.

Untuk pemakaian sehari-hari, dari folder yang sudah di-`git clone`:

```powershell
git pull --ff-only origin main
.\run-windows.bat
```

> `run-windows.bat` membuat `.venv` dan memasang dependensi utama. Jangan jalankan `.bat` tanpa awalan `./` atau `.\\` di PowerShell.

## Agar bisa diajak bicara otomatis (dua komponen terpisah)

1. **Mikrofon + pengenal suara lokal (Whisper)**: jalankan `./install-voice-windows.bat` sekali. Ini memasang `faster-whisper`, `sounddevice` dan mengunduh model multilingual **base**. Setelah model terunduh, tidak perlu jaringan untuk pengenalan suara.
2. **Pemahaman bahasa alami fleksibel (Ollama + Qwen)**: instal [Ollama Windows](https://ollama.com/download/windows). Buka PowerShell:

   ```powershell
   ollama pull qwen2.5:3b
   ```

   Atau klik `install-ai-windows.bat` sesudah memasang Ollama. Pastikan Ollama berjalan di background saat Mobius digunakan. Model diunduh **satu kali** dan diproses lokal di laptop. Tidak diperlukan API key.
3. Jalankan ulang Mobius dengan `./run-windows.bat`. Mobius **langsung mendengarkan** (tanpa menekan tombol dan tanpa masuk mode). Ucapkan **"Mobius"** di awal kalimat sebagai wake word: `"Mobius, bukain kalkulator dong"`, `"Mobius, coba cari cara bikin portfolio React"`, `"Mobius, menurut kamu kenapa laptop sering panas?"`.

**Memahami suara ≠ memahami maksud.** Whisper mentranskripsi audio; Qwen melalui Ollama memetakan bahasa informal ke tindakan yang diizinkan dan menjawab pertanyaan umum. Jika Ollama belum dipasang, perintah yang cocok dengan parser tetap berfungsi tetapi fleksibilitasnya lebih terbatas. Penggunaan pertama membutuhkan internet untuk mengunduh Python dependencies, model Whisper dan Qwen.

## Jendela yang tidak mengganggu

- Saat desktop Windows aktif (kelas jendela `Progman`/`WorkerW`): bar tampil di tengah atas layar.
- Saat Chrome/Edge, VS Code, Explorer, game atau aplikasi lain aktif: bar tersembunyi. **Mikrofon tetap mendengar**, termasuk saat bar tidak tampak.
- Untuk drag-and-drop dari File Explorer saat bar tersembunyi, seret file ke area **tengah atas layar** dan tahan gerakan sejenak. Mobius muncul sementara sebagai target drop. Bila jendela tertentu menghalangi fitur drag, gunakan tray Mobius di kanan bawah taskbar → **Tampilkan Mobius**. Tray juga menyediakan tombol on/off mikrofon.
- Ketika Mobius sedang aktif digunakan, panel konversi bisa ditampilkan dengan klik bar. Hasil tersimpan di `Documents/Mobius` (bisa diubah).
- Pemunculan saat drag menggunakan polling posisi kursor Windows; **tidak menjamin** deteksi drag di semua aplikasi, remote desktop, atau mode fullscreen. Windows 10/11 diperlukan untuk fungsi desktop visibility.

## Perintah suara contoh

| Ucapan | Hasil |
| --- | --- |
| `Mobius buka notepad dan kalkulator` | Membuka aplikasi yang termasuk daftar aman |
| `Mobius, bukain notepad dong` | Varian informal dipahami model Qwen lokal |
| `Mobius cari tutorial Python di browser` | Buka pencarian browser default |
| `Mobius ubah PDF laporan menjadi gambar` | Cari `laporan.pdf` pada Documents/Downloads/Desktop atau file yang di-drop |
| `Mobius putar musik acak` | Buka file musik acak dari `Music` |
| `Mobius matikan laptop dalam 10 menit` | **Konfirmasi wajib** sebelum menjadwalkan shutdown |
| `Mobius batalkan shutdown` | Membatalkan shutdown terjadwal |
| `Mobius jelaskan apa itu React` | Jawaban percakapan dari model AI lokal |

Tidak semua perintah Windows dapat dieksekusi. Mobius *sengaja* tidak mengizinkan model untuk menjalankan script, shell, menghapus file, atau melakukan operasi sistem tidak terdaftar. Model menghasilkan JSON yang divalidasi oleh kode aplikasi; perintah yang tidak didukung akan dijelaskan, bukan diklaim sudah dilakukan. Rencana kedepan dapat menambah keterampilan aman dan permissions sesuai kebutuhan pengguna.

## Komponen

- `mobius/ui.py`: bar, drag/drop, tray, pengelolaan mikrofon, single-panel interface.
- `mobius/desktop_visibility.py`: kebijakan tampilan hanya pada desktop aktif.
- `mobius/voice.py`: suara offline, continuous voice capture dan deteksi wake word.
- `mobius/local_ai.py`: Ollama `http://127.0.0.1:11434`, default `qwen2.5:3b`, peta intent yang tervalidasi.
- `mobius/assistant_core.py`: eksekutor Windows dan parser fallback.
- `mobius/engine.py`: konversi file lokal.
- `tests/`: uji parser, engine, keamanan AI, dan aturan visibility.

## Pengujian & build

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
.\build-windows.bat
```

Aplikasi belum diuji end-to-end langsung pada PC Windows; uji logika dilakukan dalam lingkungan pengembangan Linux. Jika mikrofon gagal, cek **Settings > Privacy & security > Microphone** dan bahwa perangkat input default berfungsi. Bila aplikasi error saat dijalankan, lihat `Documents/Mobius/mobius-error.log`.

## Catatan privasi dan keterbatasan

- Saat mic aktif, audio didengarkan secara lokal; tidak diunggah maupun disimpan ke disk oleh kode Mobius.
- Pengenalan suara awal, ketika memulai model di CPU, dapat memerlukan jeda. Whisper bukan wake-word detector khusus; ia mengonversi setiap segmen suara lalu Mobius hanya menjalankan segmen yang diawali nama Mobius. Bukan pengenalan instan dengan latensi nol.
- Beberapa program tidak tercantum dalam daftar peluncuran dan perlu ditambahkan sebagai kemampuan baru secara terkontrol.
- Offline untuk file, audio dan AI, **namun mencari halaman web jelas memerlukan internet**.
- Word ke PDF paling akurat jika Microsoft Word atau LibreOffice sudah terpasang lokal; PDF hasil scan perlu OCR untuk mengekstrak teks secara berarti.

Lisensi font tidak dibundel: gunakan Urbanist yang sudah terpasang atau fallback Segoe UI.

## v0.4: perbaikan bar yang mendadak hilang

- Bar saat startup tampil singkat selama 8 detik sehingga bisa dikenali. Ketika browser/aplikasi lain aktif, bar kembali tersembunyi setelah preview, **tetapi proses Mobius dan mikrofon tetap berjalan**.
- Klik bar atau tekan **Ctrl+Alt+M** untuk membuka panel. Panel yang sedang terbuka **tidak akan disembunyikan otomatis** saat fokus jendela berpindah; klik bar lagi untuk menutupnya. Shortcut bekerja dari aplikasi lain melalui Windows `RegisterHotKey`; apabila bentrok dengan aplikasi lain, klik ikon Mobius di **system tray** → *Tampilkan Mobius*.
- Tanpa system tray atau shortcut pemulihan, Mobius tidak disembunyikan otomatis.
- Untuk melihat error yang biasanya tersembunyi karena pythonw.exe, jalankan `run-debug-windows.bat` dari folder proyek.
- Tidak perlu memasang ulang Whisper/Ollama atau mengunduh ulang model; `git pull` hanya memperbarui source.