# MOBIUS v0.8 · Dark Carousel Island, Offline Assistant + File Studio

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
3. Jalankan ulang Mobius dengan `./run-windows.bat`. Mobius **langsung mendengarkan** tanpa membuka mode atau mengucapkan kata pemicu. Contoh: `"buka kalkulator"`, `"bukain kalkulator dong"`, dan `"cari resep rendang di browser"`.

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
## v0.5 — Robot Eyes Island (4 November 2026)

Bar kompak sekarang hanya menampilkan sepasang mata robot animasi, tanpa tulisan, label status, titik, atau chevron. Ekspresi berganti antara `O O`, `> <`, `o <`, `-- --`, dan `W W` untuk idle/mendengarkan, berpikir, berhasil, dan error. Bentuk hitamnya ditempel ke tepi atas layar seperti notch/dynamic island; panel tetap terbuka saat diperlukan dan dapat dipanggil dengan `Ctrl+Alt+M`. Ini adalah efek overlay Windows, bukan modifikasi fisik kamera atau bezel layar.

Dari clone GitHub yang sudah ada (jangan `git clone` lagi):

```powershell
cd "$HOME\\Documents\\Mobius-GitHub"
git pull --ff-only origin main
.\\run-windows.bat
```

Jika aplikasi tidak tampil, gunakan `.\\run-debug-windows.bat` atau `.\\.venv\\Scripts\\python.exe app.py` untuk melihat error. Tutup instance lama dari system tray sebelum menjalankan versi baru.

Model suara yang telah disimpan di `%USERPROFILE%\\.mobius\\models` digunakan bersama oleh semua clone. **Dependensi Python terpasang per folder `.venv`**, jadi clone baru perlu menjalankan `.\\install-voice-windows.bat` sekali jika `faster-whisper` belum terpasang pada environment tersebut. Unduhan model yang sama akan menggunakan cache lama selama masih utuh.

## v0.5.1 — Island muncul sebentar lalu hilang

**Perilaku bawaan:** Mobius menampilkan island ketika desktop Windows sedang aktif. Jika PowerShell, Chrome, atau VS Code menjadi foreground, island kompak disembunyikan agar tidak menutupi tab/aplikasi; proses asisten dan mikrofon tetap berjalan.

Untuk membuka island kapan saja: tekan **Ctrl+Alt+M**, klik **Tampilkan Mobius** pada ikon system tray, atau geser kursor ke **tepi paling atas tengah layar (0–6 px) sekitar 0,7 detik** untuk memunculkan island sementara. Saat kursor berada di atas island, island tidak disembunyikan. Panel yang terbuka manual juga tidak ditutup oleh aturan ini.

Di menu tray tersedia opsi **Sematkan island di semua aplikasi** (nonaktif secara bawaan). Aktifkan jika ingin bar tetap terlihat saat aplikasi lain terbuka; nonaktifkan lagi untuk kembali ke desktop-only. Perubahan ini tidak mengubah model suara atau folder output.

**Membedakan hide dari crash:** Bila tidak ada jendela error dan terminal debug masih sibuk, kemungkinan Mobius hanya tersembunyi. Tekan Win+D lalu cek kembali island di tengah atas. Jika aplikasi benar-benar tertutup, gunakan `run-debug-windows.bat` dan baca log `%USERPROFILE%\\Documents\\Mobius\\mobius-error.log`. Peringatan `fitz` di versi lama bukan error fatal; engine terbaru menggunakan `pymupdf`.

Update dari clone yang sudah ada:

```powershell
cd "$HOME\\Documents\\Mobius-GitHub"
git pull --ff-only origin main
.\\run-debug-windows.bat
```

Model Whisper yang sudah terunduh tetap disimpan di `%USERPROFILE%\\.mobius\\models`; tidak perlu mengunduh ulang.

## v0.6 — Wake-free voice commands + English spoken feedback

Ucapkan langsung **buka kalkulator**, **bukain Chrome dong**, atau **cari resep nasi goreng di browser**. Kata pemicu Mobius, tombol rekam, dan tab assistant tidak diperlukan.

- Microphone: local faster-whisper, adaptive audio gate, 0.8s pre-roll, 0.7s pause before transcription. Default profile is high. Set MOBIUS_MIC_SENSITIVITY=normal or low to reduce false triggers.
- Voice routing: accepts informal Indonesian verbs and normalizes phrases like 'di browser' so they are not included in Google search terms.
- Local English TTS: Windows SAPI speaks confirmations only when an app/search/music command reports success. For example, "Okay, calculator is now open" or "Okay, I opened the browser search for recipes for nasi goreng".
- While English TTS plays, microphone audio is ignored briefly to avoid the assistant hearing its own voice.
- Shutdown still requires confirmation. Without a wake word, audio from TV/videos may be recognized; disable the mic from system tray when you do not want hands-free listening.
- AI via Ollama remains optional for unsupported phrases. Web search still requires Internet to load results.

### Update an existing Git clone (no re-download of models)

1. Quit the previous Mobius instance from its system tray icon.
2. Open PowerShell and run:

```powershell
cd "$HOME\Documents\Mobius-GitHub"
git pull --ff-only origin main
.\run-debug-windows.bat
```

Previously downloaded Whisper models remain at %USERPROFILE%\.mobius\models. Your existing .venv does not need to be reinstalled.

### Test Windows microphone

```powershell
.\.venv\Scripts\python.exe -c "import sounddevice as sd; print(sd.query_devices(kind='input'))"
.\.venv\Scripts\python.exe -m pytest -q tests\test_voice_pipeline.py
```

Check Windows Settings > Privacy & security > Microphone, and enable microphone access for desktop apps. Select an English SAPI voice under Windows language/speech settings if English speech is unavailable.

GitHub Actions runs mocked command tests. Actual microphone sensitivity and speaker playback must still be validated on your Windows laptop.

### Tes mikrofon mandiri v0.6

Jalankan `./test-voice-windows.bat` dari folder repository GitHub. Script akan merekam 5 detik untuk pengujian, menampilkan RMS serta transkrip Whisper, mendeteksi intent, lalu mencoba mengucapkan satu kalimat English melalui SAPI; **tidak mengeksekusi perintah komputer**. Jika mikrofon tidak menerima 16 kHz, aplikasi mencoba sample rate perangkat (misalnya 44,1 atau 48 kHz) dan melakukan resampling lokal ke 16 kHz. Tidak ada rekaman audio yang disimpan ke disk.

## Mobius v0.7 — Living Island (November 2026)

Mobius is a Windows 10/11 desktop island **inspired by the interaction concept of Nusa** (https://rama2555.github.io/nusa/) but built from Mobius's own Qt/Python implementation, artwork and lime/emerald visual identity. No Nusa code or graphic assets are copied.

### Appearance and navigation

- Compact island attaches flush to the TOP center display edge. The flat black top and rounded bottom create a notch-like silhouette; ambient glow is emerald/green with electric lime highlights. Windows overlays cannot physically alter the laptop camera/bezel.
- Robot eyes follow cursor movement and change expressions (open, blink, focus, wink, squint, uneven eyes, W-shaped smile, drooping and sleepy). After around 95 seconds of idle, eyes get drowsy; after ~5 minutes, they doze. They wake when cursor motion resumes.
- When music plays, the compact notch extends to show a track title or (if loaded) active lyric line. While Pomodoro runs, it shows its countdown. Otherwise it displays just expressive eyes.
- Click the island or use Ctrl+Alt+M to open the integrated File Studio and four QUICK buttons: Music, Lyrics, Focus, Water. Choose a QUICK button again to hide that detail. File Studio remains on the same screen.
- As before, the island hides when another app is active unless pinned via the Mobius tray. Hover the top-center display edge for a temporary reveal.

### Music — Windows media sessions

Music controls use Windows **Global System Media Transport Controls** (GSMTC), not Spotify API or browser scraping. Spotify, Apple Music, YouTube in Chrome/Edge/Firefox and other players can work **only when their player/session exposes Windows system media controls**. Play/pause, previous/next and seek are available when supported by that player. No music account credentials are needed.

Install media support ONCE after cloning:

```powershell
cd "$HOME\Documents\Mobius-GitHub"
.\install-media-windows.bat
```

Voice examples: 'pause musik', 'lanjutkan lagu', 'skip lagu berikutnya'. Music controls will report that no player is available when Windows has no session.

### Synced lyrics

- Click **Lyrics → Open local .LRC** for offline time-coded lyrics next to your track; select a line to seek if your media player supports seeking.
- Click **Lyrics → Find lyrics online** to explicitly look up the playing track on **LRCLIB**. That action sends the track title and artist (song metadata only; duration checked locally) to LRCLIB. No account or microphone audio is sent. This feature needs internet. Some tracks lack synced lyrics.
- No copyrighted lyrics are bundled into Mobius. Only user-selected files or responses returned through LRCLIB are displayed.

### Focus timer (Pomodoro)

- Adjustable focus (5–120 min) and break (1–45 min) durations; Start/Pause/Reset and live countdown in the island.
- Original gentle local WAV chime at session transitions. Completed-session count is stored locally; running sessions are intentionally paused after a restart.
- Voice examples: 'mulai fokus 25 menit', 'pause pomodoro', 'reset timer'.

### Water reminders

- Set bottle size and daily intake goal. Click '+ Drink bottle' or say 'catat minum 250 ml'.
- Hourly intake bars, progress indicator, configurable reminder hours and interval (default 09:00–20:00, every 60 min).
- Saved only at `%USERPROFILE%\.mobius\wellness.json`; resets the daily tally on a new calendar day. No online accounts.

### Install or build on Windows

**Existing Git clone:**

```powershell
cd "$HOME\Documents\Mobius-GitHub"
git pull --ff-only origin main
.\install-media-windows.bat
.\run-debug-windows.bat
```

Whisper/AI models already downloaded remain in the user cache and do not need reinstallation. Voice setup for fresh source installs remains `install-voice-windows.bat`; the local Ollama Qwen model remains optional.

**Standalone EXE:** Run `build-windows.bat` on Windows, or open GitHub Actions → **Build Mobius Windows EXE** → Run workflow and download the EXE artifact after a successful run. `Mobius.iss` optionally builds a per-user Inno Setup installer when the compiler is available. The EXE bundles Python libraries but NOT the Whisper/Qwen model weights; those require a one-time local setup/download.

**Tests:** The GitHub Actions Windows regression workflow runs `pytest -q tests`. Checks include text/voice intent simulations, offline LRC parsing, music bridge helpers, focus transitions, water settings persistence, and Qt quick-deck startup. Music session compatibility, mic/audio playback, and packaging still need testing on the user's actual Windows laptop.

## v0.7.1 — Startup diagnosis and leaner packaging

**If PowerShell displays no window:** The default compact island deliberately hides over active browser/terminal windows. Run the debug launcher, which temporarily forces the panel to remain visible:

```powershell
cd "$HOME\Documents\Mobius-GitHub"
git pull --ff-only origin main
.\run-debug-windows.bat
```

Debug output records these stages to `%USERPROFILE%\Documents\Mobius\mobius-startup.log`: Python entrypoint, imported UI, before/after QApplication, before/after MobiusWindow, window shown, event loop. It also opens the expanded panel even when PowerShell is the foreground app. If the log stops at `Before QApplication constructor`, the issue is Windows/Qt initialization, not the island auto-hide rule.

**Isolate Qt itself:** Run `./test-qt-windows.bat` from the repo. This opens a small Qt test window, without any AI/voice/media/document modules, and closes automatically. If it cannot create QApplication, check Python/Qt environment and Qt-related environment variables before changing Mobius code. If it opens normally, compare with `mobius-startup.log` to find where Mobius stalls.

An intentional Ctrl+C produces `KeyboardInterrupt`, which **is not proof of an app crash**. The old `run-windows.bat` uses pythonw.exe and does not display console errors; use the debug launcher when troubleshooting.

**Why Nusa is ~3 MB and Mobius used to be >200 MB:** Nusa's official site describes it as a native Rust + GPU application. Mobius uses bundled Python, Qt Widgets, local document conversion libraries and faster-whisper. A PyInstaller `--onefile` executable contains the runtimes and libraries and unpacks them when launched. Models such as Whisper and Ollama are separate downloads. The packaging now depends on `PySide6-Essentials`, rather than full PySide6 (which also includes Qt Addons/WebEngine/PDF), and explicitly excludes unused Qt WebEngine/PDF widgets from the build. Actual EXE size must be measured from the new Windows CI build. Existing virtual environments are left untouched; the dependency change applies to clean installs.

Long-term alternative: a Rust native Windows island and an independently installed, on-demand local AI/document conversion worker. This is an architectural migration, not just a PyInstaller compression flag; do not expect all AI and PDF functionality in a single 3 MB file.

## v0.8 — Dark Carousel / Ambient Glances

### New compact behavior

- The notch has a **flat top attached to the top display edge** and rounded bottom, using dark charcoal/black (#030305 → #15161B). It is a Windows overlay, not a physical modification to the laptop camera bezel.
- **Robot eyes remain the default compact appearance:** cursor tracking, blink, wink, thinking, sleepy, drowsy and happy expressions.
- At approximately **38-second intervals**, a small status glimpse appears (clock/date, native Windows battery/charger percentage, focus countdown or now-playing song/lyrics if available). The glimpse **expires after 10 seconds and returns to eyes**, rather than permanently replacing the robot.
- Unplugging/connecting the charger prioritizes a battery glimpse; a focus or hydration event can briefly take the glance slot. Charger status is read through `GetSystemPowerStatus` on Windows, without network access.
- Active desktop / empty foreground → island remains visible. Browser or another foreground application → compact island hides to avoid tab overlap. **Hover at the top center edge for ~0.7 seconds** to reveal it temporarily; the expanded panel stays visible while being used. `Ctrl+Alt+M` and the tray remain alternative entry points.

### New expanded behavior

- **Separate carousel pages**, rather than mixing all tools in one long panel: Music (purple), Lyrics (sky blue), Focus Timer (amber), Water Reminder (blue), File Studio (neutral), and Assistant (soft lime). Everything uses a dark charcoal foundation rather than bright green panels.
- Navigate with the left/right arrows, six clickable indicator dots, horizontal touchpad wheel, or Shift+mouse-wheel. Feature transitions slide horizontally (360 ms); island compact↔expanded geometry morphs over 385 ms. **Expanded height adapts per page:** compact music/focus cards, medium lyrics/water cards, and a taller File Studio for the 3×3 conversion grid.
- All existing music transport controls, opt-in synced lyrics, Pomodoro, local hydration tracking, drag/drop file conversion and no-wake-word Indonesian voice commands remain accessible.
- Dragging a PDF/image/Word file to Mobius automatically selects the File Studio carousel page. The voice command to show lyrics selects the Lyrics page.

### Upgrade existing source installation

Close any running Mobius from its system tray, then open a fresh PowerShell:

```powershell
cd "$HOME\Documents\Mobius-GitHub"
git pull --ff-only origin main
.\run-debug-windows.bat
```

The debug launcher forces the panel to show even over PowerShell, useful after the earlier hidden-window issue. Once the UI works, normal launch is `.\run-windows.bat`. Keep the existing `.venv`, Whisper cache (`%USERPROFILE%\.mobius\models`) and Ollama models; **no re-download is required**.

To package as an EXE on Windows, run `.\build-windows.bat`, or download an artifact from a successful **Build Mobius Windows EXE** GitHub Actions run. The optional Inno Setup workflow generates `Mobius-Setup.exe`. The EXE includes Python/Qt libraries but does not bundle model weights.

### Verification

`tests/test_ambient_carousel.py` checks exactly ten-second glance expiry and carousel navigation. `tests/test_window_carousel_smoke.py` instantiates the actual Qt window in offscreen mode with all six feature pages, without starting microphone/media workers. Windows CI additionally runs the existing voice, PDF, hydration and lyrics tests. Real laptop interaction/rendering still needs a Windows desktop test.

## v0.8.2 — Small notch + click-away + animated browser hiding (November 4, 2026)

This revision directly addresses the screenshot/video feedback that v0.8's expanded panel occupied too much of the desktop.

- **Smaller geometry:** compact avatar 158×42 Qt logical pixels; expanded width **540** rather than 838. Page heights now fit content instead of occupying the previous oversized canvas: Music ~232px high, Focus ~245px, Lyrics ~285px, Water ~317px and File Studio ~325px (Qt logical units, before Windows display scaling). The conversion grid is a **scrollable two-column list**, so all tools stay available even though the island is much shorter.
- **Click-away:** while expanded, clicking anywhere outside the island's actual screen rectangle (desktop, browser, taskbar, etc.) collapses it without consuming the original click. Clicks inside keep the current carousel open. Native file dialogs and other modal popups are exempt.
- **Smooth hide:** switching to a foreground browser or other application after collapse shrinks the compact notch toward the camera edge (approx. 235 ms) and then hides the window. No instant disappearance.
- **Top-edge reveal:** move the pointer to the top-center ~210-pixel-wide, 6-pixel-high hover trigger for ~0.7 seconds, even while Chrome/VS Code is active. Mobius grows smoothly from a thin sliver to its compact avatar, which you can click to open the short carousel. The overlay does not steal keyboard focus on reveal.
- Desktop-only visibility remains the default. System tray pin and Ctrl+Alt+M recovery remain available. Always-on microphone, voice commands, File Studio, music/lyrics, timer and hydration modules are unchanged.

### Update from the existing Git clone

Quit the existing Mobius process from the tray icon, then run:

```powershell
cd "$HOME\Documents\Mobius-GitHub"
git pull --ff-only origin main
.\run-debug-windows.bat
```

Debug mode forces the expanded panel to remain above PowerShell so you can validate the smaller layout before normal use. Once verified, quit the debug instance from the tray and use `.\run-windows.bat` for desktop-only mode. Your existing `.venv`, Whisper cache and Ollama models are not deleted.

Run automated tests with `.\.venv\Scripts\python.exe -m pytest -q tests` if pytest is installed. Real-world mouse timings, DPI scaling, and visual animations must also be checked on a Windows desktop.

## v0.8.3 — Precision monochrome design / no emoji

The compact island is now **124×38 Qt logical pixels** with expressive white robot eyes. Battery, clock, music and timer glance widths are measured from their actual text content and capped at **240 logical pixels** (previously a rigid 370 px). The full six-page carousel is now **408 logical pixels wide**, with internal File Studio scrolling retained. Windows display scaling can make these look larger in physical pixels.

The UI uses **bright-white Segoe UI Variable text on near-black graphite**, subtle monochrome borders, reduced font sizes and restrained geometry morphing. There are no neon-green gradients or emoji-based controls. Icons for charging, time, music, lyrics, microphone, document conversion, folders, navigation and water are drawn as consistent local vectors using Qt Painter; they do not require web fonts, CDN requests, or added assets. The design takes general inspiration from the clean typography/motion of [Blurr_ Animation](https://dribbble.com/shots/12209806-Blurr-Animation), rather than copying its artwork.

No changes are required to Whisper/Ollama models. Quit the old instance from the system tray and update:

```powershell
cd "$HOME\Documents\Mobius-GitHub"
git pull --ff-only origin main
.\run-debug-windows.bat
```

Debug mode keeps the panel visible over PowerShell for inspection; use `.\run-windows.bat` for normal desktop-only behavior. Optional .exe and .iss installer packaging remain available through GitHub Actions.
