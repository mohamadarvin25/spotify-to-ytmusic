# Spotify → YouTube Music transfer

Transfer satu playlist Spotify ke YouTube Music dengan urutan **sesuai `added_at`** (waktu lagu ditambahkan ke playlist), oldest first.

## Mode

1. **Mode scraping (default)** — `src/fetch_spotify.py` + `src/transfer.py`. Bypass Spotify Developer App, ambil data via web-player pathfinder API. Pake ini kalo akun Spotify lu **gak Premium**.

2. **Mode official (deprecated)** — `src/transfer_official.py`. Pake Spotipy + OAuth resmi. Cuma jalan kalo akun Spotify yang bikin app punya **Premium** (sejak akhir 2024).

## Struktur project

```
spotify-to-ytmusic/
├── README.md
├── HOW_IT_WORKS.md           ← penjelasan logic untuk belajar
├── requirements.txt
├── examples/                 ← template config (copy ke root, isi sendiri)
│   ├── browser.example.json
│   ├── spotify_auth.example.json
│   └── spotify_oauth_config.example.json
└── src/
    ├── common.py             ← shared utilities (search, paths, UTF-8)
    ├── fetch_spotify.py      ← Step 1: ambil playlist via pathfinder
    ├── transfer.py           ← Step 2+3: search + add (batch mode)
    ├── add_batch.py          ← Re-add only (batch, kalo step 3 fail)
    ├── add_ordered.py        ← Re-add only (strict order, resumable)
    └── transfer_official.py  ← All-in-one mode resmi (deprecated)
```

File yang **gak commit** ke git (sensitif / generated):
- `browser.json`, `spotify_auth.json`, `config.json`, `.spotify_cache` — credentials
- `playlist_tracks.json`, `transfer_log.txt`, `not_found.txt`, `.add_progress` — output run

## Prasyarat
- Python 3.10+
- Akun Spotify (login di browser)
- Akun YouTube Music (login di browser; akun Google yang udah pernah aktivate YT Music)

## Setup

### 1. Install dependencies
```powershell
pip install -r requirements.txt
```

### 2. Auth YouTube Music
1. Buka https://music.youtube.com di browser, login.
2. F12 → tab **Application** → **Storage** → **Cookies** → klik `https://music.youtube.com`.
3. Copy semua cookies (Ctrl+A → Ctrl+C).
4. Copy `examples/browser.example.json` ke root sebagai `browser.json`.
5. Update field `cookie` jadi format `name1=value1; name2=value2; ...`. Field `authorization` cukup string `"SAPISIDHASH"` (akan di-replace runtime).

> Cookies YT Music ke-rotate cepet (5–30 menit pas dipake intensif). Kalo dapet 401 mid-run, tinggal re-paste cookies baru.

### 3a. Auth Spotify (mode scraping — disarankan)
1. Buka playlist lu di https://open.spotify.com.
2. F12 → **Network** → filter `pathfinder` → refresh halaman.
3. Klik request POST ke `api-partner.spotify.com/pathfinder/v2/query` dengan `operationName: fetchPlaylist`.
4. Dari **Headers**: copy `authorization` (`Bearer ...`) dan `client-token`.
5. Dari **Payload (view source)**: copy `sha256Hash` di `extensions.persistedQuery`.
6. Copy `examples/spotify_auth.example.json` ke root sebagai `spotify_auth.json`, isi token-nya.
7. Update `FETCH_PLAYLIST_HASH` di `src/fetch_spotify.py` kalo hash udah berubah.

### 3b. Auth Spotify (mode official — butuh Premium)
1. Buka https://developer.spotify.com/dashboard → Create app.
2. Redirect URI: `http://127.0.0.1:8888/callback`.
3. Copy `examples/spotify_oauth_config.example.json` ke root sebagai `config.json`, isi Client ID & Secret.

## Pemakaian

### Mode scraping
```powershell
# Step 1: fetch dari Spotify (output: playlist_tracks.json)
python -m src.fetch_spotify "https://open.spotify.com/playlist/<id>"

# Step 2+3: search di YT Music + create playlist + add tracks
python -m src.transfer "Nama Playlist Baru"
```

### Re-add (kalo step add fail di tengah)
```powershell
# Cepet, urutan kira-kira (default)
python -m src.add_batch <playlist_id>

# Lambat, urutan persis, resumable
python -m src.add_ordered <playlist_id>
python -m src.add_ordered <playlist_id> --reset   # mulai dari nol
```

### Mode official (deprecated)
```powershell
python -m src.transfer_official "https://open.spotify.com/playlist/<id>" "Nama Playlist Baru"
```

## Output
- `playlist_tracks.json` — track data dari Spotify (sorted by `added_at` asc).
- `transfer_log.txt` — log per-track (`OK<TAB>videoId<TAB>label` atau `MISS<TAB>-<TAB>label`).
- `not_found.txt` — track yang gak ketemu di YT Music.
- `.add_progress` — checkpoint untuk `add_ordered` resume.

## Catatan
- Urutan: ascending by `added_at` (oldest dulu). Mau reverse? Edit baris `tracks.sort(...)` di `src/fetch_spotify.py` jadi `reverse=True`.
- Matching: judul + artis utama + durasi. ~90–95% akurat untuk playlist umum.
- Spotify pathfinder hash bisa rotate (waktu Spotify deploy frontend baru). Kalo dapet `PersistedQueryNotFound`, ulangi step 3a.5.

## Disclaimer
Pake account session pribadi lu. **Jangan share `browser.json`, `spotify_auth.json`, atau `config.json`** ke siapapun — itu equivalent dengan login credentials. `.gitignore` udah block file-file itu.

Lihat `HOW_IT_WORKS.md` untuk penjelasan logic dan diagram arsitektur.
