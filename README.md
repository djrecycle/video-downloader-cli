# Video Downloader CLI

Aplikasi terminal interaktif untuk mendownload banyak video sekaligus. Fokus awal aplikasi ini adalah YouTube, dengan `yt-dlp` sebagai engine download.

Tampilan aplikasi dibuat sebagai UI terminal utama: saat dijalankan tanpa argumen, aplikasi membuka menu interaktif; saat dijalankan dengan argumen atau file, aplikasi tetap memakai panel status dan ringkasan yang rapi.

## Fitur

- Mode interaktif sebagai tampilan default.
- Tampilan batch tetap rapi dengan panel sesi, status per video, dan ringkasan akhir.
- Loading saat download dengan persentase, ukuran file, speed, dan ETA jika data tersedia dari `yt-dlp`.
- Bisa menerima banyak link sekaligus.
- Bisa download dari argumen, file teks, atau stdin.
- Bisa download paralel dengan jumlah worker yang bisa dipilih.
- Bisa memilih folder output.
- Bisa memilih mode video atau audio saja.
- Default video memakai kualitas stabil maksimal 1080p agar tidak otomatis mengambil 4K/AV1 yang besar dan lebih rawan gagal.
- Bisa mengaktifkan arsip agar video yang sama tidak didownload ulang.
- Bisa dry run untuk cek judul tanpa mendownload.

## Kebutuhan

- Python 3.10 atau lebih baru.
- `yt-dlp`.
- `ffmpeg` disarankan agar hasil audio/video dari YouTube bisa digabung dan mode audio saja bisa dikonversi dengan baik.

Install `ffmpeg` di Ubuntu:

```bash
sudo apt install ffmpeg
```

## Setup

Di folder proyek:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip yt-dlp
```

Launcher `./video-dl` akan otomatis memakai Python dari `.venv` jika folder `.venv` tersedia.

## Cara Pakai Utama

Jalankan:

```bash
./video-dl
```

Perintah di atas membuka tampilan interaktif. Kamu bisa juga memanggilnya secara eksplisit:

```bash
./video-dl --interactive
```

Aplikasi akan tanya dulu mau download berapa URL:

- **1** → langsung tulis satu link video.
- **banyak** → tulis path file `.txt` berisi daftar URL (satu URL per baris, baris `#` dilewati), misalnya `links.txt`.

Setelah itu aplikasi akan menanyakan:

- folder output,
- jumlah download paralel,
- mode audio saja atau video,
- apakah playlist diizinkan,
- apakah arsip download diaktifkan,
- apakah hanya cek judul tanpa download.

## Cara Pakai Cepat

Mode cepat tetap memakai tampilan terminal yang rapi, hanya tanpa prompt interaktif.

Download satu video:

```bash
./video-dl "https://www.youtube.com/watch?v=VIDEO_ID"
```

Download banyak video:

```bash
./video-dl "https://youtu.be/VIDEO_1" "https://youtu.be/VIDEO_2"
```

Download dari file `links.txt`:

```bash
./video-dl --file links.txt
```

Isi contoh `links.txt`:

```text
https://youtu.be/VIDEO_1
https://youtu.be/VIDEO_2
# baris komentar akan dilewati
https://www.youtube.com/watch?v=VIDEO_3
```

Download dari stdin:

```bash
printf '%s\n' "https://youtu.be/VIDEO_1" "https://youtu.be/VIDEO_2" | ./video-dl -
```

## Opsi Berguna

Pilih folder output:

```bash
./video-dl --output ~/Videos/youtube --file links.txt
```

Download paralel:

```bash
./video-dl --workers 3 --file links.txt
```

Audio saja:

```bash
./video-dl --audio-only --file links.txt
```

Izinkan playlist:

```bash
./video-dl --playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

Aktifkan arsip agar download tidak diulang:

```bash
./video-dl --archive downloads/archive.txt --file links.txt
```

Cek judul tanpa download:

```bash
./video-dl --dry-run --file links.txt
```

Format custom `yt-dlp` jika ingin memaksa kualitas lain:

```bash
./video-dl --format "bestvideo*+bestaudio/best" --file links.txt
```

Lihat semua opsi:

```bash
./video-dl --help
```

## Update yt-dlp

YouTube sering berubah. Jika download mulai gagal, update `yt-dlp` di virtualenv proyek:

```bash
.venv/bin/python -m pip install -U yt-dlp
```

## Catatan

Gunakan aplikasi ini hanya untuk konten yang memang boleh kamu download. Ikuti ketentuan layanan platform dan hukum yang berlaku.
