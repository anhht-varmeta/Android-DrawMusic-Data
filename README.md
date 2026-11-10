# Android-DrawMusic-Data

Data Beat Music của app **Draw Music** (`com.music.composer.draw`), phát qua CDN [jsDelivr](https://www.jsdelivr.com/)
từ repo GitHub này. App đọc URL catalog từ Firebase Remote Config (`beat_catalog_url`), nên thêm/sửa pack **không cần
update app**.

## Giới hạn jsDelivr dẫn tới cách chia repo

| Giới hạn (GitHub) | Giá trị | Hệ quả |
|---|---|---|
| Kích thước 1 version (tag/commit) | 50 MB | 20 pack ≈ 74 MB → không để chung một tag |
| Kích thước 1 file | 20 MB | mỗi pack là 1 zip ~3–5 MB, OK |
| Cache tag/commit cố định | vĩnh viễn, không purge được | file đã phát hành **không bao giờ sửa**; sửa = version mới |
| Cache branch / `@latest` | 12 giờ / 7 ngày | app không dùng branch/`latest` |

Nên data chia làm 2 phần:

- **Pack** — mỗi pack là `<id>.zip` nằm một mình trong một *orphan commit*, có tag `pack-<id>-<version>`.
  Catalog trỏ vào commit SHA đó: `https://cdn.jsdelivr.net/gh/anhht-varmeta/Android-DrawMusic-Data@<sha>/<id>.zip`.
- **Catalog** — branch `main` chỉ chứa phần nhẹ (`catalog.json`, ảnh bìa, preview ~3 MB). Mỗi lần phát hành là một
  tag semver: `https://cdn.jsdelivr.net/gh/anhht-varmeta/Android-DrawMusic-Data@1.0.0/catalog.json`.

## Cấu trúc branch `main`

```text
catalog.json                  # danh sách pack (schema bên dưới), thứ tự = thứ tự hiển thị
packs/<id>/cover.webp         # ảnh bìa 512×512
packs/<id>/preview.ogg        # loop nghe thử 16 beat
tools/beatpack-gen/           # generator (numpy) + manifest nguồn gốc + verify
tools/publish.py              # đóng zip, tạo commit/tag pack, ghi catalog, commit + tag catalog
```

## catalog.json (schema 1)

```json
{
  "schema": 1,
  "version": "1.0.0",
  "defaultPackId": "pop_sunrise",
  "packs": [
    {
      "id": "lofi_rain",
      "version": "1.0.0",
      "name": "Rainy Tape",
      "genre": "Lo-fi",
      "bpm": 80.0,
      "key": "Dm",
      "isPremium": false,
      "description": "Warm tape chords, lazy swing and vinyl crackle.",
      "cover": "packs/lofi_rain/cover.webp",
      "preview": "packs/lofi_rain/preview.ogg",
      "archive": {
        "url": "https://cdn.jsdelivr.net/gh/anhht-varmeta/Android-DrawMusic-Data@<sha>/lofi_rain.zip",
        "size": 4840000,
        "sha256": "…"
      }
    }
  ]
}
```

- `cover`/`preview`: đường dẫn **tương đối với URL của catalog** (URL tuyệt đối cũng được chấp nhận).
- `archive.url`: luôn tuyệt đối. App tải, kiểm tra `size` + `sha256`, giải nén vào bộ nhớ app.
- Zip giải nén ra đúng thư mục pack theo `docs/specs/beat-music/data-format.md` của app
  (`default.json`, `8x6.json`, `cover.webp`, `preview.ogg`, `samples/…`).
- `schema` chỉ tăng khi đổi không tương thích; app bỏ qua catalog có `schema` lạ (dùng catalog cache/bundle).
- Pack giữ `id` cố định mãi mãi (project người dùng lưu theo `packId`). Không xoá pack khỏi catalog khi app còn project
  trỏ vào nó; muốn ẩn thì thêm cờ ở schema mới.

## Thêm / sửa pack và phát hành

```bash
python3 -m venv .venv && .venv/bin/pip install -r tools/beatpack-gen/requirements.txt
# out/packs/ phải chứa đủ mọi pack đang phát hành (lần đầu: copy từ zip đã phát hành hoặc từ app)
.venv/bin/python tools/beatpack-gen/beatpack_gen.py <pack_id_mới>   # sinh pack mới vào out/packs/
python3 tools/beatpack-gen/verify_packs.py                         # manifest/sha256/size
python3 tools/publish.py 1.1.0 --dry-run
python3 tools/publish.py 1.1.0                                    # commit main + tag 1.1.0 (chưa push)
git push origin main --tags
```

Sau khi push, đổi Remote Config `beat_catalog_url` sang `…@1.1.0/catalog.json` (và cập nhật giá trị mặc định trong app
ở lần release kế). Pack không đổi giữ nguyên tag/commit cũ nên người dùng không phải tải lại.

## Pack hiện có

| id | Tên | Thể loại | BPM | Key | Version |
|---|---|---|---|---|---|
| `pop_sunrise` (mặc định, có bundle trong app) | Pop Sunrise | Pop | 118 | C | 1.0.0 |
| `hiphop_boom` | Boom Street | Hip Hop | 90 | Am | 1.0.0 |
| `edm_voltage` | Voltage | EDM | 126 | Fm | 1.0.0 |
| `lofi_rain` | Rainy Tape | Lo-fi | 80 | Dm | 1.0.0 |
| `trap_night` | Night Trap | Trap | 140 | Gm | 1.0.0 |
| `house_deep` | Deep House | House | 122 | Am | 1.0.0 |
| `drill_shadow` | Shadow Drill | Drill | 142 | F#m | 1.1.0 |
| `dnb_liquid` | Liquid Run | Drum & Bass | 174 | Em | 1.1.0 |
| `reggaeton_calor` | Calor | Reggaeton | 95 | Bbm | 1.1.0 |
| `afro_lagos` | Lagos Sun | Afrobeats | 104 | G | 1.1.0 |
| `synthwave_neon` | Neon Drive | Synthwave | 100 | Am | 1.1.0 |
| `future_prism` | Prism | Future Bass | 150 | D | 1.1.0 |
| `techno_warehouse` | Warehouse | Techno | 130 | Cm | 1.1.0 |
| `rnb_velvet` | Velvet Night | R&B | 75 | Ebm | 1.1.0 |
| `dubstep_core` | Wobble Core | Dubstep | 140 | Em | 1.1.0 |
| `disco_groove` | Disco Groove | Disco | 120 | F | 1.1.0 |
| `chill_ocean` | Ocean Drift | Chill | 95 | F | 1.1.0 |
| `phonk_drift` | Phonk Drift | Phonk | 130 | C#m | 1.1.0 |
| `jazzhop_cafe` | Coffee Jazz | Jazz Hop | 86 | Bb | 1.1.0 |
| `kpop_starlight` | Starlight | K-Pop | 128 | E | 1.1.0 |

Mọi âm thanh do `tools/beatpack-gen` tổng hợp bằng numpy, không dùng sample bên thứ ba (nguồn gốc + sha256 từng
file: `tools/beatpack-gen/manifest.json`).

## Nhạc cụ SoundFont (màn Draw)

274 nhạc cụ / 17 nhóm, tách từ **GeneralUser GS v2.0.3** (S. Christian Collins, License v2.0 — cho dùng thương mại và
đóng gói lại, xem `instruments/GeneralUser-GS-LICENSE.txt`). Mỗi nhạc cụ là `<bank>_<program>.zip` chứa đúng một
`<bank>_<program>.sf2`. 14 âm core đóng sẵn trong app, không có archive.

- Catalog: `instruments/catalog.json` trên `main`, tag `instruments-<version>`; app đọc từ Remote Config
  `instrument_catalog_url` = `https://cdn.jsdelivr.net/gh/anhht-varmeta/Android-DrawMusic-Data@instruments-1.0.0/instruments/catalog.json`.
- Archive: ~125 MB nên chia thành nhiều orphan commit ≤ 45 MB, tag `instruments-<version>-part<N>`; `archive.url` tuyệt
  đối `…@<sha>/<file>.zip`.
- Schema catalog: `docs/specs/soundfont-instruments/api-contract.md` của app.

Phát hành (sinh data bằng pipeline của app `088-AND-Draw-Music/tools/soundfont/build_catalog.py`):

```bash
python3 tools/publish_instruments.py <app>/tools/soundfont/out/instruments 1.0.0 --dry-run
python3 tools/publish_instruments.py <app>/tools/soundfont/out/instruments 1.0.0
git push origin main --tags
```
