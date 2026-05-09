# Spotify → YouTube Music transfer

Transfer satu playlist Spotify ke YouTube Music dengan urutan **sesuai `added_at`** (waktu lagu ditambahkan ke playlist), oldest first.

Project ini punya dua mode:

1. **Mode Spotify resmi (`transfer.py`)** — pake Spotify Developer App + OAuth. Sekarang Spotify wajibin app owner punya Premium, jadi mode ini gak jalan kalo akun Spotify lu free.
2. **Mode scraping (`spotify_scrape.py` + `transfer_to_ytmusic.py`)** — bypass Spotify Developer API, scrape via web-player pathfinder API pake session lu. Ini yang biasanya kepake.

## Prasyarat
- Python 3.10+
- Akun Spotify (login di browser)
- Akun YouTube Music (login di browser)

## Setup

### 1. Install dependency
```powershell
pip install -r requirements.txt
```

### 2. Auth YouTube Music
1. Buka https://music.youtube.com di browser, login.
2. F12 → tab **Application** → **Storage** → **Cookies** → klik `https://music.youtube.com`.
3. Copy semua cookies (Ctrl+A → Ctrl+C di tabel cookies).
4. Bikin file `browser.json` dari template `browser.example.json`. Update field `cookie` dengan format `name1=value1; name2=value2; ...`.

> Format `browser.json` yang valid harus include field `authorization` (boleh `"SAPISIDHASH"` placeholder), `cookie`, `user-agent`, `x-goog-authuser`, `x-origin`, `origin`. Lihat `browser.example.json`.

Cookies YT Music ke-rotate cepet (~5–30 menit kalo dipake intensif). Untuk transfer playlist besar, expect re-paste cookies di tengah jalan.

### 3a. Spotify (mode scraping — disarankan)
1. Buka playlist Spotify lu di https://open.spotify.com.
2. F12 → **Network** → filter `pathfinder`.
3. Refresh halaman.
4. Klik salah satu request POST ke `api-partner.spotify.com/pathfinder/v2/query` yang `operationName: fetchPlaylist`.
5. Dari **Headers**, copy nilai `authorization` (`Bearer ...`) dan `client-token`.
6. Dari **Payload (view source)**, copy `sha256Hash` di dalam `extensions.persistedQuery`.
7. Bikin `spotify_auth.json`:
   ```json
   {
     "authorization": "Bearer xxxxx",
     "client_token": "xxxxx"
   }
   ```
8. Update konstanta `FETCH_PLAYLIST_HASH` di `spotify_scrape.py` kalo hash-nya udah berubah.

### 3b. Spotify (mode resmi)
Cuma jalan kalo akun Spotify yang bikin app punya Premium. Bikin app di https://developer.spotify.com/dashboard, redirect URI `http://127.0.0.1:8888/callback`, copy ke `config.json` (template di `config.example.json`).

## Cara pakai

### Mode scraping
```powershell
# 1. Fetch tracks dari Spotify (output: playlist_tracks.json, sorted by added_at asc)
python spotify_scrape.py "https://open.spotify.com/playlist/<id>"

# 2. Transfer ke YT Music (search + create playlist + add tracks batch-50)
python transfer_to_ytmusic.py "Nama Playlist Baru" "deskripsi opsional"
```

### Mode resmi
```powershell
python transfer.py "https://open.spotify.com/playlist/<id>" "Nama Playlist Baru"
```

### Add ulang ke playlist yang udah ada
Kalo step add gagal (cookies expired) tapi search udah selesai (`transfer_log.txt` ada):
```powershell
# Mode batch (cepet, urutan kira-kira)
python add_only.py <playlist_id>

# Mode strict order (lambat, urutan persis sesuai log; resumable via .add_progress)
python add_strict_order.py <playlist_id>
python add_strict_order.py <playlist_id> --reset   # mulai dari nol
```

## Output
- `playlist_tracks.json` — data lagu mentah dari Spotify (sorted by `added_at` asc).
- `transfer_log.txt` — log per-lagu (OK + videoId | MISS).
- `not_found.txt` — lagu yang gak ketemu di YT Music.
- `.add_progress` — checkpoint untuk resume `add_strict_order.py`.

## Catatan
- Urutan: ascending by `added_at` (lagu paling lama di atas). Mau reverse? Edit baris `tracks.sort(...)` jadi `reverse=True`.
- Matching: judul + artis utama + durasi (±3 detik bonus skor). 90–95% akurat untuk playlist umum.
- Cookies YT Music kadang expire mid-process pas batch besar. `add_strict_order.py` resumable, `transfer_to_ytmusic.py` belom.
- Spotify pathfinder hash bisa rotate. Kalo dapet `PersistedQueryNotFound`, ulangi step 3a.6 buat dapet hash baru.

## Disclaimer
Pake account session pribadi lu. Jangan share `browser.json`, `spotify_auth.json`, atau `config.json` ke siapapun — itu equivalent sama login credentials lu. `.gitignore` udah block file-file itu.
