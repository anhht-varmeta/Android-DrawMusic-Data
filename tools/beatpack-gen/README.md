# beatpack-gen

Sinh các Beat pack vào `out/packs/` (không commit) — BEAT-040..042, phát hành qua `tools/publish.py`. Mọi âm thanh được tổng hợp
bằng numpy (sine/noise/additive), **không** dùng sample của bên thứ ba (BEAT-041). Chạy trên máy dev, không vào APK.

## Cài đặt

```bash
python3 -m venv .venv && .venv/bin/pip install -r tools/beatpack-gen/requirements.txt   # chạy ở root repo data
```

`soundfile` mang sẵn libsndfile có Vorbis (ffmpeg Homebrew thường thiếu `libvorbis`).

## Chạy

```bash
.venv/bin/python tools/beatpack-gen/beatpack_gen.py              # sinh lại cả 20 pack
.venv/bin/python tools/beatpack-gen/beatpack_gen.py lofi_rain    # chỉ 1 pack
python3 tools/beatpack-gen/verify_packs.py                       # kiểm tra manifest/size (BEAT-T041/T042)
```

Mỗi lần chạy ghi lại `manifest.json` (nguồn + sha256 từng file). File thêm tay (pack mua license) phải thêm entry
`{"source": "licensed", "license": "<tên/URL license>", "sha256": "..."}` nếu không `verify_packs.py` sẽ báo lỗi.
Ogg có serial ngẫu nhiên nên hash đổi mỗi lần sinh — luôn commit `manifest.json` cùng asset.

## Pack

| id | Thể loại | BPM | Key |
|---|---|---|---|
| `pop_sunrise` (mặc định) | Pop | 118 | C |
| `hiphop_boom` | Hip Hop | 90 | Am |
| `edm_voltage` | EDM | 126 | Fm |
| `lofi_rain` | Lo-fi | 80 | Dm |
| `trap_night` | Trap | 140 | Gm |
| `house_deep` | House | 122 | Am |
| `drill_shadow` | Drill | 142 | F#m |
| `dnb_liquid` | Drum & Bass | 174 | Em |
| `reggaeton_calor` | Reggaeton | 95 | Bbm |
| `afro_lagos` | Afrobeats | 104 | G |
| `synthwave_neon` | Synthwave | 100 | Am |
| `future_prism` | Future Bass | 150 | D |
| `techno_warehouse` | Techno | 130 | Cm |
| `rnb_velvet` | R&B | 75 | Ebm |
| `dubstep_core` | Dubstep | 140 | Em |
| `disco_groove` | Disco | 120 | F |
| `chill_ocean` | Chill | 95 | F |
| `phonk_drift` | Phonk | 130 | C#m |
| `jazzhop_cafe` | Jazz Hop | 86 | Bb |
| `kpop_starlight` | K-Pop | 128 | E |

Mỗi pack: 48 loop (8 cột × 6 hàng: Drums, Kick, Tops = 8 beat; Bass, Chords, Lead, Pad = 16 beat; FX & Vox = 8 beat),
48 one-shot, 48 sequence `.drum` (gọi pad one-shot), `Song_8x6.song` 64 beat, `preview.ogg` 16 beat, `cover.webp`.
Thứ tự trong `index.json` = thứ tự hiển thị; pack đầu là pack mặc định (BEAT-021). Định dạng:
`docs/specs/beat-music/data-format.md`.

> Không sinh lại pack đã phát hành (Ogg có serial ngẫu nhiên → zip khác → `publish.py` dừng vì tag đã có). Muốn sửa
> một pack đã phát hành thì đổi `version` của pack đó rồi publish catalog mới. 6 pack đầu là bản 1.0.0 lấy nguyên từ app;
> 14 pack sau sinh bằng generator 1.1.0. Thứ tự `PACKS` giữ cố định vì seed = vị trí trong danh sách.
