#!/usr/bin/env python3
"""Generate the bundled Beat Music packs (BEAT-040..042).

Every sound is synthesised here from sine/noise primitives with numpy — no third-party samples
(BEAT-041). Output follows docs/specs/beat-music/data-format.md and is written to
app/src/main/assets/beatpacks/<packId>/, plus tools/beatpack-gen/manifest.json (source + sha256 of
each file, checked by verify_packs.py).

Usage (from the repo root):
    python3 tools/beatpack-gen/beatpack_gen.py            # all packs
    python3 tools/beatpack-gen/beatpack_gen.py pop_sunrise # one pack (manifest keeps the others)

Needs: Python 3.10+ and tools/beatpack-gen/requirements.txt (numpy, Pillow, soundfile).
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter

GENERATOR_VERSION = "1.1.0"
SR = 44100
TICKS_PER_BEAT = 500
TICKS_PER_STEP = 125
COLS, ROWS = 8, 6
OGG_COMPRESSION = 0.7  # libsndfile: Vorbis quality = 1 - level -> q3, ~112 kbps stereo

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "out/packs"
MANIFEST = Path(__file__).resolve().parent / "manifest.json"

MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]


# ───────────────────────────── pack definitions ─────────────────────────────

@dataclass
class Genre:
    id: str
    name: str
    genre: str
    bpm: float
    key: str
    root: int  # MIDI note of the tonic used for bass (octave 2-3)
    minor: bool
    progression: list[int]  # scale degrees, one chord per bar (4 bars)
    sevenths: bool
    swing: float  # 0 = straight, 0.5 = full triplet swing on odd 16ths
    kick: list[str]
    snare: list[str]
    hat: list[str]
    open_hat: str
    perc: list[str]
    kick_kind: str  # "punch" | "808" | "soft" | "club"
    bass_kind: str  # "saw" | "square" | "sine" | "808" | "pluck"
    chord_kind: str  # "stab" | "keys" | "pluck"
    lead_kind: str  # "pluck" | "saw" | "bell" | "square"
    pad_kind: str  # "warm" | "airy" | "dark"
    reverb: float
    lofi: bool
    colors: tuple[tuple[int, int, int], tuple[int, int, int]]
    description: str
    extra: dict = field(default_factory=dict)


PACKS: list[Genre] = [
    Genre(
        id="pop_sunrise", name="Pop Sunrise", genre="Pop", bpm=118, key="C", root=48, minor=False,
        progression=[0, 4, 5, 3], sevenths=False, swing=0.0,
        kick=["x.....x.x.......", "x.....x...x.x...", "x...x...x...x..."],
        snare=["....x.......x...", "....x.......x..o"],
        hat=["x.x.x.x.x.x.x.x.", "xoxoxoxoxoxoxoxo"], open_hat="..............x.",
        perc=["..x.....x...x...", "...x..x....x..x."],
        kick_kind="punch", bass_kind="pluck", chord_kind="keys", lead_kind="pluck", pad_kind="warm",
        reverb=0.18, lofi=False, colors=((255, 138, 101), (255, 214, 102)),
        description="Bright, upbeat pop grooves with sunny keys and plucks.",
    ),
    Genre(
        id="hiphop_boom", name="Boom Street", genre="Hip Hop", bpm=90, key="Am", root=45, minor=True,
        progression=[0, 5, 2, 6], sevenths=True, swing=0.18,
        kick=["x......x..x.....", "x.........x..x..", "x..x......x....."],
        snare=["....x.......x...", "....x..o....x..."],
        hat=["x.x.x.x.x.x.x.x.", "x.xxx.x.x.xxx.x."], open_hat="......x.........",
        perc=["...x.......x....", ".x.....x...x...x"],
        kick_kind="punch", bass_kind="sine", chord_kind="keys", lead_kind="bell", pad_kind="dark",
        reverb=0.15, lofi=False, colors=((92, 107, 192), (240, 98, 146)),
        description="Dusty boom-bap drums, round bass and moody keys.",
    ),
    Genre(
        id="edm_voltage", name="Voltage", genre="EDM", bpm=126, key="Fm", root=41, minor=True,
        progression=[0, 5, 2, 6], sevenths=False, swing=0.0,
        kick=["x...x...x...x...", "x...x...x...x.x."],
        snare=["....x.......x...", "....x.......xxxx"],
        hat=["..x...x...x...x.", "xxxxxxxxxxxxxxxx"], open_hat="..x...x...x...x.",
        perc=["x.x.x.x.x.x.x.x.", "...x...x...x..x."],
        kick_kind="club", bass_kind="saw", chord_kind="stab", lead_kind="saw", pad_kind="airy",
        reverb=0.22, lofi=False, colors=((0, 229, 255), (124, 77, 255)),
        description="Festival energy: four-on-the-floor, supersaw stabs and risers.",
    ),
    Genre(
        id="lofi_rain", name="Rainy Tape", genre="Lo-fi", bpm=80, key="Dm", root=50, minor=True,
        progression=[3, 6, 2, 5], sevenths=True, swing=0.25,
        kick=["x.......x.x.....", "x......x..x....."],
        snare=["....x.......x...", "....x.......x.o."],
        hat=["x.x.x.x.x.x.x.x.", "x.xox.x.x.xox.x."], open_hat="................",
        perc=[".....x.......x..", "..x.......x....."],
        kick_kind="soft", bass_kind="sine", chord_kind="keys", lead_kind="bell", pad_kind="warm",
        reverb=0.3, lofi=True, colors=((141, 110, 99), (255, 183, 77)),
        description="Warm tape chords, lazy swing and vinyl crackle.",
    ),
    Genre(
        id="trap_night", name="Night Trap", genre="Trap", bpm=140, key="Gm", root=43, minor=True,
        progression=[0, 0, 5, 4], sevenths=False, swing=0.0,
        kick=["x......x..x.....", "x.....x...x..x..", "x.......x.x....."],
        snare=["........x.......", "........x......o"],
        hat=["x.x.x.x.x.x.x.x.", "xxxxxxxxx.xxxxxx", "x.x.xxx.x.x.xxxx"], open_hat="..............x.",
        perc=["...x.....x......", ".......x.....x.."],
        kick_kind="808", bass_kind="808", chord_kind="pluck", lead_kind="bell", pad_kind="dark",
        reverb=0.2, lofi=False, colors=((38, 50, 56), (229, 57, 53)),
        description="Hard 808s, rolling hats and dark bells.",
    ),
    Genre(
        id="house_deep", name="Deep House", genre="House", bpm=122, key="Am", root=45, minor=True,
        progression=[0, 6, 5, 6], sevenths=True, swing=0.08,
        kick=["x...x...x...x...", "x...x...x...x..x"],
        snare=["....x.......x...", "....x.......x..."],
        hat=["..x...x...x...x.", "x.xxx.xxx.xxx.xx"], open_hat="..x...x...x...x.",
        perc=["x.xxx.xxx.xxx.xx", "...x..x....x..x."],
        kick_kind="club", bass_kind="square", chord_kind="stab", lead_kind="square", pad_kind="airy",
        reverb=0.25, lofi=False, colors=((0, 150, 136), (63, 81, 181)),
        description="Late-night house: deep bass, organ stabs and shakers.",
    ),
    # ── 1.1.0: 14 more packs (keep the 6 above first so their seeds never change) ──
    Genre(
        id="drill_shadow", name="Shadow Drill", genre="Drill", bpm=142, key="F#m", root=42, minor=True,
        progression=[0, 5, 0, 6], sevenths=False, swing=0.0,
        kick=["x.........x.....", "x......x..x.....", "x.....x.....x..."],
        snare=["........x.....x.", "...o....x.....x."],
        hat=["x..x..x.x..x..x.", "x.xx..x.x..xx.x.", "x..x.xx.x..x..xx"], open_hat="................",
        perc=["......x.......x.", "..x.......x....."],
        kick_kind="808", bass_kind="808", chord_kind="pluck", lead_kind="bell", pad_kind="dark",
        reverb=0.22, lofi=False, colors=((33, 33, 33), (96, 125, 139)),
        description="Sliding 808s, skippy hats and cold drill bells.",
    ),
    Genre(
        id="dnb_liquid", name="Liquid Run", genre="Drum & Bass", bpm=174, key="Em", root=40, minor=True,
        progression=[0, 5, 3, 6], sevenths=True, swing=0.0,
        kick=["x.........x.....", "x.........x..x.."],
        snare=["....x.......x...", "....x.......x.o."],
        hat=["x.x.x.x.x.x.x.x.", "xxxxxxxxxxxxxxxx"], open_hat="..............x.",
        perc=["..x...x...x...x.", ".x.x...x.x...x.."],
        kick_kind="punch", bass_kind="sine", chord_kind="keys", lead_kind="pluck", pad_kind="airy",
        reverb=0.28, lofi=False, colors=((0, 188, 212), (0, 77, 64)),
        description="Rolling breaks, deep subs and liquid pads.",
    ),
    Genre(
        id="reggaeton_calor", name="Calor", genre="Reggaeton", bpm=95, key="Bbm", root=46, minor=True,
        progression=[0, 5, 2, 6], sevenths=False, swing=0.0,
        kick=["x...x...x...x...", "x...x...x...x..x"],
        snare=["...x..x....x..x.", "...x..x....x.xx."],
        hat=["x.x.x.x.x.x.x.x.", "x.xxx.xxx.xxx.xx"], open_hat="......x.......x.",
        perc=["..x...x...x...x.", ".x..x..x.x..x..x"],
        kick_kind="punch", bass_kind="808", chord_kind="pluck", lead_kind="pluck", pad_kind="warm",
        reverb=0.16, lofi=False, colors=((255, 87, 34), (233, 30, 99)),
        description="Dembow rhythm, punchy kicks and tropical plucks.",
    ),
    Genre(
        id="afro_lagos", name="Lagos Sun", genre="Afrobeats", bpm=104, key="G", root=43, minor=False,
        progression=[0, 3, 4, 3], sevenths=True, swing=0.12,
        kick=["x.....x...x.....", "x..x..x...x....."],
        snare=["...x..x....x..x.", "...x.......x...."],
        hat=["x.xxx.xxx.xxx.xx", "x.x.x.x.x.x.x.x."], open_hat="......x.........",
        perc=["x..x..x...x..x..", "..x..x....x..x.x"],
        kick_kind="soft", bass_kind="pluck", chord_kind="pluck", lead_kind="bell", pad_kind="warm",
        reverb=0.18, lofi=False, colors=((255, 193, 7), (76, 175, 80)),
        description="Bouncy afro percussion, log-drum bass and bright guitars.",
    ),
    Genre(
        id="synthwave_neon", name="Neon Drive", genre="Synthwave", bpm=100, key="Am", root=45, minor=True,
        progression=[0, 5, 2, 6], sevenths=False, swing=0.0,
        kick=["x.......x.......", "x.......x.x....."],
        snare=["....x.......x...", "....x.......x..o"],
        hat=["x.x.x.x.x.x.x.x.", "xxxxxxxxxxxxxxxx"], open_hat="..............x.",
        perc=["....x.......x...", "..x...x...x...x."],
        kick_kind="punch", bass_kind="saw", chord_kind="stab", lead_kind="saw", pad_kind="airy",
        reverb=0.32, lofi=False, colors=((255, 64, 129), (63, 81, 181)),
        description="Retro 80s drive: gated drums, arps and lush pads.",
    ),
    Genre(
        id="future_prism", name="Prism", genre="Future Bass", bpm=150, key="D", root=50, minor=False,
        progression=[3, 4, 5, 0], sevenths=True, swing=0.0,
        kick=["x.........x.....", "x......x..x....."],
        snare=["........x.......", "........x.....oo"],
        hat=["x.x.x.x.x.x.x.x.", "x.xxx.x.x.xxx.x."], open_hat="......x.......x.",
        perc=["..x.......x.....", "....x..x....x..x"],
        kick_kind="club", bass_kind="saw", chord_kind="stab", lead_kind="square", pad_kind="airy",
        reverb=0.26, lofi=False, colors=((129, 212, 250), (206, 147, 216)),
        description="Wobbly supersaw chords, vocal chops and big drops.",
    ),
    Genre(
        id="techno_warehouse", name="Warehouse", genre="Techno", bpm=130, key="Cm", root=36, minor=True,
        progression=[0, 0, 5, 6], sevenths=False, swing=0.0,
        kick=["x...x...x...x...", "x...x...x...x.x."],
        snare=["....x.......x...", "................"],
        hat=["..x...x...x...x.", "x.xxx.xxx.xxx.xx"], open_hat="..x...x...x...x.",
        perc=["x..x..x..x..x..x", ".x...x...x...x.."],
        kick_kind="club", bass_kind="square", chord_kind="stab", lead_kind="square", pad_kind="dark",
        reverb=0.3, lofi=False, colors=((66, 66, 66), (0, 230, 118)),
        description="Driving warehouse techno: rumbling kicks and acid lines.",
    ),
    Genre(
        id="rnb_velvet", name="Velvet Night", genre="R&B", bpm=75, key="Ebm", root=39, minor=True,
        progression=[0, 3, 6, 5], sevenths=True, swing=0.2,
        kick=["x......x..x.....", "x.........x..x.."],
        snare=["....x.......x...", "....x..o....x..."],
        hat=["x.x.x.x.x.x.x.x.", "x.xxx.x.x.xxx.xx"], open_hat="..............x.",
        perc=["...x.......x....", "......x.......x."],
        kick_kind="soft", bass_kind="sine", chord_kind="keys", lead_kind="bell", pad_kind="warm",
        reverb=0.26, lofi=False, colors=((106, 27, 154), (255, 112, 67)),
        description="Smooth slow jams with silky keys and round bass.",
    ),
    Genre(
        id="dubstep_core", name="Wobble Core", genre="Dubstep", bpm=140, key="Em", root=40, minor=True,
        progression=[0, 0, 5, 3], sevenths=False, swing=0.0,
        kick=["x.........x.....", "x.....x...x....."],
        snare=["........x.......", "........x.....x."],
        hat=["x.x.x.x.x.x.x.x.", "x..x..x.x..x..x."], open_hat="......x.........",
        perc=["....x.......x...", "..x.......x..x.."],
        kick_kind="punch", bass_kind="square", chord_kind="stab", lead_kind="saw", pad_kind="dark",
        reverb=0.2, lofi=False, colors=((118, 255, 3), (49, 27, 146)),
        description="Half-time heavy drums, growling bass and dark stabs.",
    ),
    Genre(
        id="disco_groove", name="Disco Groove", genre="Disco", bpm=120, key="F", root=41, minor=False,
        progression=[0, 5, 1, 4], sevenths=True, swing=0.05,
        kick=["x...x...x...x...", "x...x...x...x..."],
        snare=["....x.......x...", "....x.......x..o"],
        hat=["..x...x...x...x.", "xxxxxxxxxxxxxxxx"], open_hat="..x...x...x...x.",
        perc=["x.x.x.x.x.x.x.x.", "...x..x....x..x."],
        kick_kind="club", bass_kind="pluck", chord_kind="stab", lead_kind="pluck", pad_kind="warm",
        reverb=0.2, lofi=False, colors=((255, 214, 0), (213, 0, 249)),
        description="Funky disco: octave bass, string stabs and open hats.",
    ),
    Genre(
        id="chill_ocean", name="Ocean Drift", genre="Chill", bpm=95, key="F", root=41, minor=False,
        progression=[0, 3, 5, 4], sevenths=True, swing=0.1,
        kick=["x.......x.......", "x.....x...x....."],
        snare=["....x.......x...", "....x.......x..."],
        hat=["x.x.x.x.x.x.x.x.", "x.xox.x.x.xox.x."], open_hat="................",
        perc=["..x.....x.......", ".....x.......x.."],
        kick_kind="soft", bass_kind="sine", chord_kind="pluck", lead_kind="bell", pad_kind="airy",
        reverb=0.34, lofi=False, colors=((0, 131, 143), (178, 235, 242)),
        description="Laid-back chill beats with airy pads and soft plucks.",
    ),
    Genre(
        id="phonk_drift", name="Phonk Drift", genre="Phonk", bpm=130, key="C#m", root=37, minor=True,
        progression=[0, 0, 5, 4], sevenths=False, swing=0.0,
        kick=["x......x..x.....", "x.....x...x..x.."],
        snare=["....x.......x...", "....x.......x.x."],
        hat=["x.x.x.x.x.x.x.x.", "xxxxxxxxxxxxxxxx"], open_hat="......x.......x.",
        perc=["x.x.x.x.x.x.x.x.", "..xx..x...xx..x."],
        kick_kind="808", bass_kind="808", chord_kind="pluck", lead_kind="bell", pad_kind="dark",
        reverb=0.18, lofi=True, colors=((136, 14, 79), (26, 35, 126)),
        description="Drift phonk: distorted 808s, cowbells and tape grit.",
    ),
    Genre(
        id="jazzhop_cafe", name="Coffee Jazz", genre="Jazz Hop", bpm=86, key="Bb", root=46, minor=False,
        progression=[1, 4, 0, 5], sevenths=True, swing=0.28,
        kick=["x.......x.x.....", "x......x...x...."],
        snare=["....x.......x...", "....x..o....x..o"],
        hat=["x.x.x.x.x.x.x.x.", "x.xxx.xxx.xxx.xx"], open_hat="................",
        perc=["...x.......x....", ".x.....x...x...."],
        kick_kind="soft", bass_kind="sine", chord_kind="keys", lead_kind="bell", pad_kind="warm",
        reverb=0.24, lofi=True, colors=((121, 85, 72), (255, 224, 178)),
        description="Swinging jazz chords, upright-style bass and dusty drums.",
    ),
    Genre(
        id="kpop_starlight", name="Starlight", genre="K-Pop", bpm=128, key="E", root=40, minor=False,
        progression=[0, 4, 5, 3], sevenths=False, swing=0.0,
        kick=["x...x...x...x...", "x.....x.x...x..."],
        snare=["....x.......x...", "....x.......x.xx"],
        hat=["x.x.x.x.x.x.x.x.", "xxxxxxxxxxxxxxxx"], open_hat="..x...x...x...x.",
        perc=["..x...x...x...x.", "...x..x....x..x."],
        kick_kind="club", bass_kind="pluck", chord_kind="pluck", lead_kind="square", pad_kind="airy",
        reverb=0.2, lofi=False, colors=((255, 128, 171), (124, 77, 255)),
        description="Glossy idol-pop energy: tight drums and sparkling synths.",
    ),
]


# Genres whose main backbeat is a clap (snare column = clap) and the perc voice of each genre.
CLAP_GENRES = ("EDM", "House", "Trap", "Drill", "Reggaeton", "Future Bass", "Techno", "Disco", "Phonk", "K-Pop")
PERC_BY_GENRE = {
    "Pop": "shaker", "Hip Hop": "rim", "EDM": "snap", "Lo-fi": "rim", "Trap": "snap", "House": "shaker",
    "Drill": "rim", "Drum & Bass": "shaker", "Reggaeton": "rim", "Afrobeats": "shaker", "Synthwave": "snap",
    "Future Bass": "snap", "Techno": "rim", "R&B": "snap", "Dubstep": "snap", "Disco": "shaker",
    "Chill": "shaker", "Phonk": "rim", "Jazz Hop": "rim", "K-Pop": "snap",
}


# ───────────────────────────── DSP helpers ─────────────────────────────

def ts(n: int) -> np.ndarray:
    return np.arange(n) / SR


def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def fft_filter(x: np.ndarray, lo: float | None = None, hi: float | None = None, order: int = 2) -> np.ndarray:
    """Zero-phase Butterworth-shaped filter in the frequency domain (circular)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    h = np.ones_like(f)
    if hi:
        h /= np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        h /= np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(spec * h, n=len(x))


class Synth:
    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)

    def noise(self, n: int) -> np.ndarray:
        return self.rng.uniform(-1, 1, n)

    # drums -----------------------------------------------------------------
    def kick(self, kind: str, var: int = 0) -> np.ndarray:
        p = {
            "punch": dict(f0=160, f1=50, sweep=35, decay=9, dur=0.45, drive=2.0, click=0.35),
            "club": dict(f0=180, f1=48, sweep=40, decay=7, dur=0.5, drive=2.6, click=0.25),
            "soft": dict(f0=120, f1=52, sweep=28, decay=11, dur=0.4, drive=1.3, click=0.12),
            "808": dict(f0=150, f1=45, sweep=25, decay=2.2, dur=1.2, drive=1.8, click=0.2),
        }[kind]
        p = dict(p)
        p["f1"] *= 1 + 0.06 * (var - 2)
        p["decay"] *= 1 + 0.12 * (var % 3 - 1)
        n = int(p["dur"] * SR)
        t = ts(n)
        f = p["f1"] + (p["f0"] - p["f1"]) * np.exp(-t * p["sweep"])
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * p["decay"])
        y += fft_filter(self.noise(n), lo=1500) * np.exp(-t * 300) * p["click"]
        y = np.tanh(y * p["drive"]) / np.tanh(p["drive"])
        return y

    def snare(self, var: int = 0) -> np.ndarray:
        n = int(0.35 * SR)
        t = ts(n)
        tone_f = 180 + 15 * var
        tone = np.sin(2 * np.pi * tone_f * t) * np.exp(-t * 30)
        nz = fft_filter(self.noise(n), lo=1200 + 200 * var, hi=9000) * np.exp(-t * (16 + 3 * var))
        return np.tanh(1.6 * (0.55 * tone + 0.9 * nz))

    def clap(self, var: int = 0) -> np.ndarray:
        n = int(0.4 * SR)
        t = ts(n)
        env = np.zeros(n)
        for k, off in enumerate([0, 0.011, 0.022, 0.031][: 3 + var % 2]):
            s = int(off * SR)
            env[s:] += np.exp(-(t[: n - s]) * (180 if k < 2 else 14))
        nz = fft_filter(self.noise(n), lo=900 + 150 * var, hi=5500)
        return np.tanh(1.4 * nz * env)

    def hat(self, open_: bool, var: int = 0) -> np.ndarray:
        n = int((0.6 if open_ else 0.12) * SR)
        t = ts(n)
        nz = fft_filter(self.noise(n), lo=6500 + 600 * var, order=3)
        metal = sum(np.sign(np.sin(2 * np.pi * f * t)) for f in (3140, 4720, 6080, 8020)) * 0.08
        decay = 7 if open_ else 55 + 10 * var
        return (nz + fft_filter(metal, lo=6000)) * np.exp(-t * decay) * 0.8

    def perc(self, kind: str) -> np.ndarray:
        if kind == "rim":
            n = int(0.12 * SR); t = ts(n)
            y = (np.sin(2 * np.pi * 820 * t) + 0.5 * np.sin(2 * np.pi * 1700 * t)) * np.exp(-t * 60)
            return y + fft_filter(self.noise(n), lo=2000) * np.exp(-t * 400) * 0.4
        if kind == "tom":
            n = int(0.5 * SR); t = ts(n)
            f = 110 + 90 * np.exp(-t * 18)
            return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
        if kind == "shaker":
            n = int(0.18 * SR); t = ts(n)
            env = (1 - np.exp(-t * 120)) * np.exp(-t * 28)
            return fft_filter(self.noise(n), lo=4500, hi=13000) * env
        if kind == "cowbell":
            n = int(0.3 * SR); t = ts(n)
            y = np.sign(np.sin(2 * np.pi * 562 * t)) + np.sign(np.sin(2 * np.pi * 845 * t))
            return fft_filter(y, lo=500, hi=4000) * np.exp(-t * 14) * 0.5
        if kind == "conga":
            n = int(0.35 * SR); t = ts(n)
            f = 330 + 60 * np.exp(-t * 40)
            return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16)
        if kind == "snap":
            n = int(0.15 * SR); t = ts(n)
            return fft_filter(self.noise(n), lo=1800, hi=6500) * np.exp(-t * 70) * 1.3
        raise ValueError(kind)

    def crash(self, reverse: bool = False) -> np.ndarray:
        n = int(1.6 * SR)
        t = ts(n)
        y = fft_filter(self.noise(n), lo=4200) * np.exp(-t * 2.6) * 0.7
        return y[::-1].copy() if reverse else y

    # tonal -----------------------------------------------------------------
    def tone(self, freq: float, dur: float, wave: str, cutoff: float = 4000, bright_decay: float = 0.0,
             attack: float = 0.005, release: float = 0.08, decay: float = 0.0, sustain: float = 1.0,
             detune: float = 0.0, voices: int = 1, max_h: int = 48) -> np.ndarray:
        n = int((dur + release) * SR)
        t = ts(n)
        y = np.zeros(n)
        for v in range(voices):
            f = freq * (1 + detune * (v - (voices - 1) / 2))
            nh = max(1, min(max_h, int(min(SR / 2.3, cutoff * 4) / f)))
            for k in range(1, nh + 1):
                if wave == "sine" and k > 1:
                    break
                if wave in ("square", "tri") and k % 2 == 0:
                    continue
                a = {"saw": 1 / k, "square": 1 / k, "tri": 1 / k ** 2, "sine": 1.0}[wave]
                a /= math.sqrt(1 + (k * f / cutoff) ** 4)
                partial = np.sin(2 * np.pi * k * f * t + self.rng.uniform(0, 2 * np.pi))
                if bright_decay:
                    partial *= np.exp(-t * bright_decay * (k - 1) ** 0.8)
                y += a * partial
        y /= voices
        env = np.ones(n)
        a_n = max(1, int(attack * SR))
        env[:a_n] = np.linspace(0, 1, a_n)
        if decay:
            env[a_n:] = sustain + (1 - sustain) * np.exp(-(t[a_n:] - attack) / decay)
        rel_start = int(dur * SR)
        env[rel_start:] *= np.exp(-(t[rel_start:] - dur) / max(release / 4, 1e-3))
        return y * env

    def vowel(self, freq: float, dur: float, vowel: str) -> np.ndarray:
        formants = {"a": (730, 1090, 2440), "e": (530, 1840, 2480), "i": (300, 2290, 3010),
                    "o": (570, 840, 2410), "u": (320, 870, 2240)}[vowel]
        n = int(dur * SR)
        t = ts(n)
        vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t)
        phase = 2 * np.pi * np.cumsum(freq * vib) / SR
        y = np.zeros(n)
        for k in range(1, int(4000 / freq)):
            fk = k * freq
            w = sum(a * math.exp(-((fk - F) / 110) ** 2) for F, a in zip(formants, (1.0, 0.6, 0.3)))
            y += (w + 0.01) / k ** 0.3 * np.sin(k * phase)
        env = np.minimum(1, t / 0.02) * np.minimum(1, (dur - t) / 0.06).clip(0)
        return y * env

    # effects ----------------------------------------------------------------
    def reverb(self, stereo: np.ndarray, amount: float, length: float = 1.6) -> np.ndarray:
        """Circular convolution reverb, so loop tails wrap into the loop start."""
        if amount <= 0:
            return stereo
        n = stereo.shape[0]
        ir_n = min(n, int(length * SR))
        out = stereo.copy()
        for c in range(2):
            ir = np.zeros(n)
            t = ts(ir_n)
            ir[:ir_n] = self.noise(ir_n) * np.exp(-t * 6.9 / length)
            ir[:ir_n] = fft_filter(ir[:ir_n], hi=5000)
            ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
            wet = np.fft.irfft(np.fft.rfft(stereo[:, c]) * np.fft.rfft(ir), n=n)
            out[:, c] = stereo[:, c] + amount * wet
        return out


def mix(*sigs: np.ndarray) -> np.ndarray:
    """Sums mono signals of different lengths (zero-padded to the longest)."""
    out = np.zeros(max(len(x) for x in sigs))
    for x in sigs:
        out[: len(x)] += x
    return out


def place(buf: np.ndarray, sig: np.ndarray, pos: int, gain: float = 1.0, pan: float = 0.5) -> None:
    """Adds mono [sig] into stereo [buf] at [pos]; overflow wraps to the start (seamless loops)."""
    n = buf.shape[0]
    lg, rg = math.cos(pan * math.pi / 2) * math.sqrt(2), math.sin(pan * math.pi / 2) * math.sqrt(2)
    idx = (pos + np.arange(len(sig))) % n
    np.add.at(buf[:, 0], idx, sig * gain * lg)
    np.add.at(buf[:, 1], idx, sig * gain * rg)


def normalize(x: np.ndarray, peak: float = 0.89) -> np.ndarray:
    m = np.max(np.abs(x))
    return x if m < 1e-9 else x * (peak / m)


def soft_clip(x: np.ndarray) -> np.ndarray:
    return np.tanh(x * 1.1) / np.tanh(1.1)


def to_stereo(mono: np.ndarray, pan: float = 0.5) -> np.ndarray:
    buf = np.zeros((len(mono), 2))
    place(buf, mono, 0, 1.0, pan)
    return buf


# ───────────────────────────── music helpers ─────────────────────────────

class Theory:
    def __init__(self, g: Genre):
        self.g = g
        self.scale = MINOR if g.minor else MAJOR

    def degree(self, d: int, octave_base: int) -> int:
        o, i = divmod(d, 7)
        return octave_base + self.scale[i] + 12 * o

    def chord(self, deg: int, base: int, sevenths: bool | None = None, inversion: int = 0) -> list[int]:
        size = 4 if (self.g.sevenths if sevenths is None else sevenths) else 3
        notes = [self.degree(deg + 2 * k, base) for k in range(size)]
        for _ in range(inversion):
            notes = notes[1:] + [notes[0] + 12]
        return notes


def parse_steps(pattern: str) -> list[tuple[int, float]]:
    return [(i, {"x": 1.0, "X": 1.15, "o": 0.45}[c]) for i, c in enumerate(pattern) if c in "xXo"]


# ───────────────────────────── pack builder ─────────────────────────────

class PackBuilder:
    def __init__(self, g: Genre, seed: int):
        self.g = g
        self.s = Synth(seed)
        self.rng = np.random.default_rng(seed + 1)
        self.th = Theory(g)
        self.beat_n = 60 / g.bpm * SR
        self.step_n = self.beat_n / 4
        self.audio: dict[str, np.ndarray] = {}
        self.sample_meta: dict[str, dict] = {}
        self.drums: dict[str, str] = {}
        self.loop_pads: list[dict] = []
        self.shot_pads: list[dict] = []
        self.seq_pads: list[dict] = []
        self.shot_index: dict[str, tuple[int, int]] = {}
        self.kit = self._make_kit()

    # one-shot kit, also used to render drum loops -------------------------------
    def _make_kit(self) -> dict[str, np.ndarray]:
        g, s = self.g, self.s
        kit = {
            "kick": s.kick(g.kick_kind, 2), "kick_b": s.kick("soft" if g.kick_kind != "soft" else "punch", 1),
            "snare": s.snare(1), "clap": s.clap(1), "hat": s.hat(False, 1), "ohat": s.hat(True, 1),
            "rim": s.perc("rim"), "shaker": s.perc("shaker"), "tom": s.perc("tom"),
            "cowbell": s.perc("cowbell"), "conga": s.perc("conga"), "snap": s.perc("snap"),
        }
        if g.lofi:
            for k in kit:
                kit[k] = fft_filter(kit[k], hi=6500)
        return kit

    def step_pos(self, step: int) -> int:
        swing = self.g.swing * self.step_n if step % 2 == 1 else 0
        return int(round(step * self.step_n + swing))

    # loops ---------------------------------------------------------------------
    def drum_loop(self, beats: int, layers: list[tuple[str, str, float, float]], fill: bool = False) -> np.ndarray:
        n = int(round(beats * self.beat_n))
        buf = np.zeros((n, 2))
        bars = beats // 4
        for bar in range(bars):
            for sound, pattern, gain, pan in layers:
                pat = pattern
                if fill and bar == bars - 1 and sound in ("snare", "tom"):
                    pat = pattern[:12] + "xoxx" if sound == "snare" else "............x.xx"
                for step, vel in parse_steps(pat):
                    jitter = self.rng.uniform(0.92, 1.0)
                    place(buf, self.kit[sound], self.step_pos(bar * 16 + step), gain * vel * jitter, pan)
        if self.g.lofi:
            buf += to_stereo(self.crackle(n) * 0.04)
        return buf

    def crackle(self, n: int) -> np.ndarray:
        y = fft_filter(self.s.noise(n), lo=200, hi=3000) * 0.15
        pops = self.rng.random(n) < 4 / SR * 8
        y[pops] += self.rng.uniform(-1, 1, pops.sum())
        return y

    def tonal_loop(self, beats: int, events: list[tuple[float, float, int, float]], voice) -> np.ndarray:
        """events: (start_beat, length_beats, midi, velocity)."""
        n = int(round(beats * self.beat_n))
        buf = np.zeros((n, 2))
        for start, length, midi, vel in events:
            sig = voice(midi_hz(midi), length * 60 / self.g.bpm)
            pos = int(round(start * self.beat_n + (self.g.swing * self.step_n if (start * 4) % 2 == 1 else 0)))
            place(buf, sig, pos, vel, 0.5)
        return buf

    def bass_voice(self, kind: str):
        s = self.s
        if kind == "808":
            def v(f, d):
                t = ts(int((d + 0.1) * SR))
                y = np.sin(2 * np.pi * f * t) * np.exp(-t * 0.9)
                y = np.tanh(2.2 * y)
                return y * np.minimum(1, t / 0.004)
            return v
        if kind == "sine":
            return lambda f, d: mix(np.tanh(1.4 * s.tone(f, d, "sine", attack=0.008, release=0.06)),
                                    0.15 * s.tone(f * 2, d, "tri", cutoff=900, release=0.06))
        if kind == "saw":
            return lambda f, d: s.tone(f, d, "saw", cutoff=900, bright_decay=6, voices=2, detune=0.006,
                                       release=0.05, decay=0.25, sustain=0.7)
        if kind == "square":
            return lambda f, d: s.tone(f, d, "square", cutoff=700, bright_decay=4, release=0.04,
                                       decay=0.2, sustain=0.6)
        return lambda f, d: s.tone(f, min(d, 0.6), "saw", cutoff=1200, bright_decay=12, release=0.05,
                                   decay=0.18, sustain=0.3)

    def chord_voice(self, kind: str):
        s = self.s
        if kind == "stab":
            return lambda f, d: s.tone(f, min(d, 0.35), "saw", cutoff=2600, bright_decay=5, voices=3,
                                       detune=0.012, release=0.12, decay=0.2, sustain=0.4, max_h=24)
        if kind == "pluck":
            return lambda f, d: s.tone(f, min(d, 0.5), "square", cutoff=3000, bright_decay=14, release=0.2,
                                       decay=0.15, sustain=0.1, max_h=24)
        # keys: electric piano-ish, tine partial + body
        return lambda f, d: mix(s.tone(f, d, "tri", cutoff=2200, bright_decay=3, release=0.25, decay=0.6,
                                       sustain=0.35, max_h=16),
                                0.25 * s.tone(f * 4.0, min(d, 0.2), "sine", release=0.1, decay=0.08, sustain=0))

    def lead_voice(self, kind: str):
        s = self.s
        if kind == "saw":
            return lambda f, d: s.tone(f, d, "saw", cutoff=3500, voices=3, detune=0.01, release=0.12,
                                       decay=0.3, sustain=0.6, max_h=32)
        if kind == "bell":
            return lambda f, d: mix(s.tone(f, min(d, 0.8), "sine", release=0.6, decay=0.35, sustain=0.0),
                                    0.35 * s.tone(f * 2.76, min(d, 0.4), "sine", release=0.3, decay=0.15, sustain=0))
        if kind == "square":
            return lambda f, d: s.tone(f, d, "square", cutoff=2500, bright_decay=6, release=0.1, decay=0.2,
                                       sustain=0.5, max_h=24)
        return lambda f, d: s.tone(f, min(d, 0.4), "saw", cutoff=4000, bright_decay=10, release=0.15,
                                   decay=0.12, sustain=0.15, max_h=32)

    def pad_voice(self, kind: str):
        s = self.s
        cutoff = {"warm": 1400, "airy": 3200, "dark": 800}[kind]
        return lambda f, d: s.tone(f, d, "saw", cutoff=cutoff, voices=3, detune=0.008, attack=0.35,
                                   release=0.6, max_h=20)

    # columns -------------------------------------------------------------------
    def add_audio(self, name: str, stereo: np.ndarray, kind: str, beats: float, instrument: int,
                  reverb: float = 0.0, peak: float = 0.7) -> str:
        if reverb:
            stereo = self.s.reverb(stereo, reverb)
        if self.g.lofi and kind == "loop":
            stereo = np.stack([fft_filter(stereo[:, c], hi=5200) for c in range(2)], axis=1)
        stereo = normalize(soft_clip(normalize(stereo, 1.0)), peak)
        self.audio[name] = stereo
        self.sample_meta[name] = {
            "name": name, "displayName": name, "type": kind, "mediaTypeId": 1, "instrumentId": instrument,
            "bpm": self.g.bpm if kind == "loop" else 0.0, "beats": float(beats),
            "duration": round(stereo.shape[0] / SR, 4), "key": self.g.key if instrument >= 3 else "",
            "start": 0.0, "end": 1.0, "attack": 0.0, "decay": 0.0, "sustain": 1.0, "releas": 0.0, "user": False,
        }
        return name

    def build_loops(self) -> None:
        g = self.g
        k = lambda i: g.kick[i % len(g.kick)]
        sn = lambda i: g.snare[i % len(g.snare)]
        h = lambda i: g.hat[i % len(g.hat)]
        pc = lambda i: g.perc[i % len(g.perc)]
        snare_snd = "clap" if g.genre in CLAP_GENRES else "snare"
        perc_snd = PERC_BY_GENRE[g.genre]

        drums = [
            [("kick", k(0), 1.0, 0.5), ("hat", h(0), 0.4, 0.55)],
            [("kick", k(0), 1.0, 0.5), (snare_snd, sn(0), 0.8, 0.5), ("hat", h(0), 0.4, 0.55)],
            [("kick", k(1), 1.0, 0.5), (snare_snd, sn(1), 0.8, 0.5), ("hat", h(1), 0.4, 0.55),
             (perc_snd, pc(0), 0.35, 0.35)],
            [("kick", k(2), 1.0, 0.5), (snare_snd, sn(0), 0.8, 0.5), ("snare", sn(0), 0.35, 0.5),
             ("hat", h(len(g.hat) - 1), 0.38, 0.6), ("ohat", g.open_hat, 0.3, 0.45)],
            [("kick", "x.......x.......", 1.0, 0.5), (snare_snd, "........x.......", 0.8, 0.5),
             ("hat", "x...x...x...x...", 0.4, 0.55)],
            [("kick", k(1), 1.0, 0.5), (snare_snd, sn(1), 0.8, 0.5), ("hat", h(0), 0.4, 0.55),
             ("tom", "................", 0.6, 0.4), ("snare", "................", 0.6, 0.5)],
        ]
        names = ["Beat Lite", "Beat Main", "Beat Groove", "Beat Full", "Beat Half", "Beat Fill"]
        for r, layers in enumerate(drums):
            loop = self.drum_loop(8, layers, fill=(r == 5))
            self._loop_pad(r, 0, self.add_audio(f"{names[r]}", loop, "loop", 8, 0, reverb=g.reverb * 0.3))

        kicks = [k(0), k(1), k(2), "x...x...x...x...", "x.......x.......", "x..x..x...x..x.."]
        for r, pat in enumerate(kicks):
            layers = [("kick", pat, 1.0, 0.5)]
            if r >= 3:
                layers.append(("kick_b", "..x...x...x...x." if r == 3 else "......x.......x.", 0.5, 0.5))
            self._loop_pad(r, 1, self.add_audio(f"Kick {r + 1}", self.drum_loop(8, layers), "loop", 8, 1))

        tops = [
            [("hat", h(0), 0.5, 0.6)], [("hat", h(-1), 0.5, 0.6), ("ohat", g.open_hat, 0.35, 0.4)],
            [("shaker", "xxxxxxxxxxxxxxxx", 0.45, 0.65)], [(perc_snd, pc(0), 0.5, 0.35), ("hat", h(0), 0.35, 0.6)],
            [("conga", pc(1), 0.55, 0.3), ("rim", pc(0), 0.35, 0.7)],
            [("cowbell", "..x.....x.x.....", 0.35, 0.6), ("shaker", "x.x.x.x.x.x.x.x.", 0.4, 0.4)],
        ]
        for r, layers in enumerate(tops):
            loop = self.drum_loop(8, layers)
            self._loop_pad(r, 2, self.add_audio(f"Tops {r + 1}", loop, "loop", 8, 2, reverb=g.reverb * 0.4))

        self._bass_column()
        self._chord_column()
        self._lead_column()
        self._pad_column()
        self._fx_column()

    def _prog_roots(self) -> list[int]:
        return [self.th.degree(d, self.g.root) for d in self.g.progression]

    def _bass_column(self) -> None:
        g = self.g
        voice = self.bass_voice(g.bass_kind)
        rhythms = [
            [(0, 4)],
            [(0, 1.5), (1.5, 1), (2.5, 1.5)],
            [(i * 0.5, 0.45) for i in range(8)],
            [(0, 0.75), (0.75, 0.75), (2, 0.5), (3, 0.5), (3.5, 0.5)],
            [(0, 0.5), (0.5, 0.5, 12), (1.5, 0.5), (2, 0.5, 12), (3, 0.5), (3.5, 0.5, 12)],
            [(0, 0.25), (0.75, 0.25), (1.5, 0.75), (2.5, 0.25), (3, 1)],
        ]
        if g.bass_kind == "808":
            rhythms[2] = [(0, 1.5), (1.75, 0.5), (2.5, 1.5)]
        for r, rhythm in enumerate(rhythms):
            events = []
            for bar, root in enumerate(self._prog_roots()):
                for item in rhythm:
                    start, length = item[0], item[1]
                    shift = item[2] if len(item) > 2 else 0
                    events.append((bar * 4 + start, length, root + shift, 0.9))
            loop = self.tonal_loop(16, events, voice)
            self._loop_pad(r, 3, self.add_audio(f"Bass {r + 1}", loop, "loop", 16, 3))

    def _chord_column(self) -> None:
        g, th = self.g, self.th
        voice = self.chord_voice(g.chord_kind)
        rhythms = [
            [(0, 4)], [(0, 1.5), (1.5, 2.5)], [(i, 0.5) for i in range(4)] + [(3.5, 0.5)],
            [(0.5, 0.5), (1.5, 0.5), (2.5, 0.5), (3.5, 0.5)], [(0, 0.75), (0.75, 0.75), (1.5, 2.5)],
            [(0, 2), (2.5, 0.5), (3, 1)],
        ]
        base = g.root + 12
        for r, rhythm in enumerate(rhythms):
            events = []
            for bar, deg in enumerate(g.progression):
                notes = th.chord(deg, base, inversion=(r + bar) % 2)
                for start, length in rhythm:
                    events += [(bar * 4 + start, length, m, 0.5) for m in notes]
            loop = self.tonal_loop(16, events, voice)
            self._loop_pad(r, 4, self.add_audio(f"Chords {r + 1}", loop, "loop", 16, 4, reverb=g.reverb))

    def _lead_column(self) -> None:
        g, th = self.g, self.th
        voice = self.lead_voice(g.lead_kind)
        base = g.root + 24
        for r in range(ROWS):
            events = []
            if r in (0, 1):  # arpeggios
                order = [0, 1, 2, 1] if r == 0 else [0, 2, 1, 3]
                step = 0.5 if r == 0 else 0.25
                for bar, deg in enumerate(g.progression):
                    notes = th.chord(deg, base, sevenths=True)
                    for i in range(int(4 / step)):
                        events.append((bar * 4 + i * step, step * 0.9, notes[order[i % 4] % len(notes)], 0.55))
            else:  # seeded melodies on chord/scale tones
                rhythm_bank = [[0, 1, 1.5, 2, 3], [0, 0.5, 1, 2.5, 3, 3.5], [0, 1.5, 3], [0, 0.75, 1.5, 2.25, 3]]
                rhythm = rhythm_bank[r - 2]
                degree = 4
                for bar, chord_deg in enumerate(g.progression):
                    for i, start in enumerate(rhythm):
                        nxt = rhythm[i + 1] if i + 1 < len(rhythm) else 4
                        if i == 0:
                            degree = chord_deg + 7 + int(self.rng.choice([0, 2, 4]))
                        else:
                            degree += int(self.rng.choice([-2, -1, 1, 2]))
                            degree = int(np.clip(degree, 3, 14))
                        events.append((bar * 4 + start, (nxt - start) * 0.9, th.degree(degree, g.root + 12), 0.6))
            loop = self.tonal_loop(16, events, voice)
            loop = self._echo(loop, 0.75 if r % 2 == 0 else 0.5, 0.3)
            self._loop_pad(r, 5, self.add_audio(f"Lead {r + 1}", loop, "loop", 16, 5, reverb=g.reverb))

    def _echo(self, buf: np.ndarray, beats: float, fb: float) -> np.ndarray:
        d = int(round(beats * self.beat_n))
        out = buf.copy()
        tap = buf
        for i in range(3):
            tap = np.roll(tap, d, axis=0) * fb
            out[:, i % 2] += tap[:, i % 2]
        return out

    def _pad_column(self) -> None:
        g, th = self.g, self.th
        for r in range(ROWS):
            kind = [g.pad_kind, g.pad_kind, "airy", "dark", "warm", g.pad_kind][r]
            voice = self.pad_voice(kind)
            base = g.root + (12 if r < 3 else 24)
            events = []
            if r == 5:  # drone on the tonic
                events = [(0, 16, g.root + 12, 0.5), (0, 16, g.root + 19, 0.4)]
            else:
                for bar, deg in enumerate(g.progression):
                    events += [(bar * 4, 4, m, 0.4) for m in th.chord(deg, base, inversion=r % 3)]
            loop = self.tonal_loop(16, events, voice)
            self._loop_pad(r, 6, self.add_audio(f"Pad {r + 1}", loop, "loop", 16, 6, reverb=g.reverb + 0.2))

    def _fx_column(self) -> None:
        g, s = self.g, self.s
        n8 = int(round(8 * self.beat_n))
        t = ts(n8)
        # 1 riser: filtered noise + rising tone over 8 beats
        rise = np.linspace(0, 1, n8) ** 2
        riser = fft_filter(s.noise(n8), lo=800, hi=9000) * rise * 0.6
        riser += np.sin(2 * np.pi * np.cumsum(200 + 1600 * rise) / SR) * rise * 0.3
        # 2 downlifter
        fall = np.linspace(1, 0, n8) ** 2
        down = (fft_filter(s.noise(n8), lo=600, hi=8000) * 0.5 +
                np.sin(2 * np.pi * np.cumsum(120 + 1400 * fall) / SR) * 0.3) * fall
        # 3 impact + tail
        impact = np.zeros(n8)
        boom = s.kick("808", 0)[: n8]
        impact[: len(boom)] += boom
        tail = s.crash()
        impact[: len(tail)] += tail * 0.8
        fx = [("Riser", to_stereo(riser)), ("Downlifter", to_stereo(down)), ("Impact", to_stereo(impact))]
        # 4/5 vocal chops on chord tones
        vowels = ["a", "o", "e", "i", "u"]
        for r, rhythm in ((3, [0, 1.5, 3, 4.5, 6]), (4, [0, 0.75, 2, 2.75, 4, 5.5, 6.5])):
            buf = np.zeros((n8, 2))
            for i, start in enumerate(rhythm):
                deg = g.progression[int(start // 4) % len(g.progression)] + [0, 2, 4, 7][i % 4]
                sig = s.vowel(midi_hz(self.th.degree(deg, g.root + 24)), 0.35 * 60 / g.bpm * 2, vowels[i % 5])
                place(buf, sig, int(start * self.beat_n), 0.6, 0.35 + 0.3 * (i % 2))
            fx.append((f"Vox Chop {r - 2}", self._echo(buf, 0.75, 0.25)))
        # 6 texture: vinyl / wind sweep
        if g.lofi:
            tex = to_stereo(self.crackle(n8) * 0.6 + fft_filter(s.noise(n8), hi=900) * 0.15)
        else:
            sweep = 0.5 + 0.5 * np.sin(2 * np.pi * t / (t[-1] + 1e-9))
            tex = np.stack([fft_filter(s.noise(n8), lo=300, hi=2500) * sweep,
                            fft_filter(s.noise(n8), lo=300, hi=2500) * (1 - sweep)], axis=1) * 0.5
        fx.append(("Texture", tex))
        for r, (name, audio) in enumerate(fx):
            self._loop_pad(r, 7, self.add_audio(name, audio, "loop", 8, 7, reverb=g.reverb + 0.1, peak=0.65))

    def _loop_pad(self, row: int, col: int, name: str) -> None:
        self.loop_pads.append(pad(row, col, name, play_mode=0, gain=[0.9, 0.9, 0.8, 0.85, 0.7, 0.7, 0.6, 0.7][col]))

    # one-shots -----------------------------------------------------------------
    def build_shots(self) -> None:
        g, s, th = self.g, self.s, self.th
        cols: list[list[tuple[str, np.ndarray, int]]] = []  # (name, mono, chokeGroup)
        cols.append([(f"Kick Hit {i + 1}", s.kick([g.kick_kind, "punch", "club", "soft", "808", g.kick_kind][i], i), 0)
                     for i in range(ROWS)])
        cols.append([(f"Snare Hit {i + 1}", s.snare(i), 0) for i in range(ROWS)])
        cols.append([(f"Clap Hit {i + 1}", s.clap(i) if i < 4 else s.perc("snap"), 0) for i in range(ROWS)])
        cols.append([("Hat Closed", s.hat(False, 0), 1), ("Hat Tight", s.hat(False, 3), 1),
                     ("Hat Open", s.hat(True, 0), 1), ("Hat Pedal", s.hat(False, 5) * 0.7, 1),
                     ("Crash", s.crash(), 0), ("Reverse Crash", s.crash(reverse=True), 0)])
        cols.append([(name.title(), s.perc(name), 0) for name in ("rim", "tom", "shaker", "cowbell", "conga", "snap")])
        bass = self.bass_voice(g.bass_kind)
        cols.append([(f"Bass Note {i + 1}", bass(midi_hz(th.degree([0, 2, 3, 4, 5, 7][i], g.root)), 0.5), 0)
                     for i in range(ROWS)])
        chord = self.chord_voice("stab" if g.chord_kind == "keys" else g.chord_kind)
        stabs = []
        for i, deg in enumerate([0, 1, 2, 3, 4, 5]):
            notes = th.chord(deg, g.root + 12)
            stabs.append((f"Stab {i + 1}", mix(*[chord(midi_hz(m), 0.4) for m in notes]) / len(notes), 0))
        cols.append(stabs)
        vox = [(f"Vox {v.upper()}", s.vowel(midi_hz(th.degree(i * 2, g.root + 24)), 0.45, v), 0)
               for i, v in enumerate(["a", "e", "o", "u"])]
        n_laser = int(0.4 * SR)
        laser = np.sin(2 * np.pi * np.cumsum(np.geomspace(3000, 200, n_laser)) / SR) * np.exp(-ts(n_laser) * 6)
        boom = mix(s.kick("808", 4), s.crash()[: int(1.2 * SR)] * 0.5)
        cols.append(vox + [("Laser", laser, 0), ("Boom", boom, 0)])

        for c, column in enumerate(cols):
            for r, (name, mono, choke) in enumerate(column):
                stereo = to_stereo(mono)
                if c in (6, 7):
                    stereo = self.s.reverb(np.pad(stereo, ((0, int(0.8 * SR)), (0, 0))), self.g.reverb + 0.1)
                self.add_audio(name, stereo, "oneshot", 0, c, peak=0.62)
                self.shot_pads.append(pad(r, c, name, play_mode=3, gain=0.9, choke=choke))
                self.shot_index[name] = (r, c)

    # sequences (.drum) -----------------------------------------------------------
    def build_sequences(self) -> None:
        g = self.g
        def notes_for(steps_by_cell: list[tuple[tuple[int, int], str]], beats: int) -> dict:
            notes = []
            for (row, col), pattern in steps_by_cell:
                full = (pattern * (beats * 4 // len(pattern) + 1))[: beats * 4]
                for step, vel in parse_steps(full):
                    notes.append((step, vel, row, col))
            notes.sort(key=lambda n: (n[0], n[3], n[2]))
            return sequence_json(beats, [(st * TICKS_PER_STEP, TICKS_PER_STEP, v, r, c, 1) for st, v, r, c in notes])

        snare_col = 2 if g.genre in CLAP_GENRES else 1
        kick_pats = (g.kick + ["x...x...x...x...", "x.......x.......", "x..x..x...x..x..", "x.x...x...x....."])[:ROWS]
        hat_pats = (g.hat + ["xxxxxxxxxxxxxxxx", "x.x.x.x.x.x.x.x.", "..x...x...x...x.", "x.xxx.xxx.xxx.xx"])[:ROWS]
        cols = [
            [[((r % 3, 0), kick_pats[r])] for r in range(ROWS)],
            [[((r % 2, snare_col), g.snare[r % len(g.snare)] if r < 4 else "....x..x....x...")] for r in range(ROWS)],
            [[((0 if r < 3 else 1, 3), hat_pats[r]), ((2, 3), g.open_hat if r % 2 else "................")]
             for r in range(ROWS)],
            [[((r, 4), g.perc[r % len(g.perc)])] for r in range(ROWS)],
            [[((0, 0), kick_pats[r % len(g.kick)]), ((0, snare_col), g.snare[r % len(g.snare)]),
              ((0, 3), hat_pats[r % len(g.hat)])] for r in range(ROWS)],
        ]
        names = ["Kick Seq", "Snare Seq", "Hats Seq", "Perc Seq", "Kit Seq"]
        for c, column in enumerate(cols):
            for r, cells in enumerate(column):
                beats = 4 if r < 3 else 8
                name = f"{names[c]} {r + 1}"
                self._add_seq(r, c, name, notes_for(cells, beats), beats)

        # tonal sequences: bass notes / stabs following the progression, vox one-shots
        degree_to_row = {0: 0, 2: 1, 3: 2, 4: 3, 5: 4, 7: 5}
        for c, (label, shot_col, rhythms) in enumerate([
            ("Bass Seq", 5, ["x.....x.x.......", "x..x..x...x.x...", "x.x.x.x.x.x.x.x.",
                             "x.......x.......", "x..x....x..x..x.", "x.....x...x.x..."]),
            ("Stab Seq", 6, ["x...............", "x.....x.........", "..x...x...x...x.",
                             "x..x..x.........", "x.x.....x.x.....", "....x.......x..."]),
            ("Vox Seq", 7, ["x.......x.......", "x..x....x.....x.", "x...x...x...x...",
                            "..x.....x.x.....", "x.....x.....x...", "x..x..x..x..x..."]),
        ], start=5):
            for r, rhythm in enumerate(rhythms):
                events = []
                for bar, deg in enumerate(g.progression):
                    for step, vel in parse_steps(rhythm):
                        if shot_col == 7:
                            row = (bar + step // 4) % 4
                        elif shot_col == 6:
                            row = min(deg % 7, ROWS - 1)
                        else:
                            d = deg % 7
                            row = degree_to_row.get(d, degree_to_row.get(d - 1, 0))
                            row = min(row, ROWS - 1)
                        events.append(((bar * 16 + step) * TICKS_PER_STEP, TICKS_PER_STEP * 2, vel, row, shot_col, 1))
                self._add_seq(r, c, f"{label} {r + 1}", sequence_json(16, events), 16)

    def _add_seq(self, row: int, col: int, name: str, seq: dict, beats: int) -> None:
        self.drums[name] = json.dumps(seq, indent=1)
        self.sample_meta[name] = {
            "name": name, "displayName": name, "type": "sequence", "mediaTypeId": 6, "instrumentId": col,
            "bpm": self.g.bpm, "beats": float(beats), "duration": round(beats * 60 / self.g.bpm, 4),
            "key": "", "start": 0.0, "end": 1.0, "attack": 0.0, "decay": 0.0, "sustain": 1.0, "releas": 0.0,
            "user": False,
        }
        self.seq_pads.append(pad(row, col, name, play_mode=0, gain=1.0))

    # song + preview --------------------------------------------------------------
    def song(self) -> dict:
        sections = [  # (start, end, row, col)
            (0, 16, 0, 6), (0, 16, 0, 2), (8, 16, 0, 7),
            (16, 64, 0, 6), (16, 32, 1, 0), (16, 48, 0, 3), (16, 32, 0, 4),
            (32, 48, 3, 0), (32, 64, 1, 4), (32, 64, 0, 5), (32, 48, 1, 2),
            (48, 64, 2, 0), (48, 64, 1, 3), (48, 64, 3, 7),
        ]
        events = [(s * TICKS_PER_BEAT, (e - s) * TICKS_PER_BEAT, 1.0, r, c, 0) for s, e, r, c in sections]
        events.sort(key=lambda e: (e[0], e[4]))
        return sequence_json(64, events)

    def preview(self) -> np.ndarray:
        """16-beat demo: drums Groove + bass 1 + chords 1 + lead 1 + pad 1."""
        n = int(round(16 * self.beat_n))
        mix = np.zeros((n, 2))
        for name, gain in (("Beat Groove", 0.9), ("Bass 1", 0.8), ("Chords 1", 0.6), ("Lead 1", 0.5),
                           ("Pad 1", 0.45)):
            a = self.audio[name]
            reps = int(math.ceil(n / a.shape[0]))
            mix += np.tile(a, (reps, 1))[:n] * gain
        fade = int(0.3 * SR)
        mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
        return normalize(soft_clip(mix), 0.75)

    def session(self) -> dict:
        names = ["Drums", "Kick", "Tops", "Bass", "Chords", "Lead", "Pad", "FX & Vox"]
        tracks = [{
            "col": c, "name": names[c], "level": 0.8, "filter": 0.5, "eq_bass": 0.5, "eq_mid": 0.5,
            "eq_treb": 0.5, "effect_name": "", "effect_x": 0.5, "effect_y": 0.5, "effect_lock": False,
            "colorId": c, "mute": False, "solo": False,
        } for c in range(COLS)]
        sort = lambda pads: sorted(pads, key=lambda p: (p["line"], p["col"]))
        return {
            "column_number": COLS, "row_number": ROWS, "effect_name": "", "effect_x": 0.5, "effect_y": 0.5,
            "effect_lock": False, "bi_filter": False, "tracks": tracks,
            "grids": [{"grid_type": 0, "pads": sort(self.loop_pads)}, {"grid_type": 1, "pads": sort(self.shot_pads)},
                      {"grid_type": 2, "pads": sort(self.seq_pads)}],
            "song": {"sampleName": "Song_8x6"},
        }


def pad(row: int, col: int, name: str, play_mode: int, gain: float, choke: int = 0) -> dict:
    return {
        "line": row, "col": col, "sampleName": name, "playMode": play_mode, "quantize": -1.0, "gain": gain,
        "pan": 0.5, "pitch": 0.0, "reverse": False, "repeat": False, "chokeGroup": choke, "linkGroup": 0,
        "linkLauncher": False, "mixerChannel": col, "biFilter": False, "start": 0.0, "end": 1.0,
    }


def sequence_json(beats: float, events: list[tuple[float, float, float, int, int, int]]) -> dict:
    notes = []
    for i, (start, length, vel, row, col, grid) in enumerate(events):
        notes.append({
            "id": i + 1, "eventStart": float(start), "eventEnd": float(start + length), "duration": float(length),
            "startSet": True, "endSet": True, "enabled": True, "velocity": round(min(1.0, vel), 3),
            "deltaRoll": -1.0, "pitchOffsetInSemitones": 0, "repeatStartInTicks": -1.0,
            "eventStartAbsoluteOffset": 0.0, "grid": grid, "row": row, "column": col,
        })
    return {"lengthInBeats": float(beats), "notes": notes}


# ───────────────────────────── output ─────────────────────────────

def write_ogg(path: Path, stereo: np.ndarray) -> None:
    """Encodes Vorbis; lossy coding can overshoot noisy transients, so re-encode quieter until it fits."""
    audio = np.clip(stereo, -1, 1).astype(np.float32)
    for _ in range(4):
        sf.write(str(path), audio, SR, format="OGG", subtype="VORBIS", compression_level=OGG_COMPRESSION)
        decoded, _ = sf.read(str(path), dtype="float32")
        peak = float(np.max(np.abs(decoded)))
        if peak <= 0.97:
            return
        audio = audio * (0.95 / peak)


def write_cover(path: Path, g: Genre, seed: int) -> None:
    size = 512
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size] / size
    tgrad = (x * 0.6 + y * 0.4)[..., None]
    c0, c1 = np.array(g.colors[0]), np.array(g.colors[1])
    img = (c0 * (1 - tgrad) + c1 * tgrad).astype(np.uint8)
    im = Image.fromarray(img, "RGB")
    over = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    cx, cy = rng.uniform(0.55, 0.8) * size, rng.uniform(0.2, 0.45) * size
    for i in range(7):
        r = 40 + i * 34
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 70 - i * 8), width=6)
    bars = 24
    for i in range(bars):
        h = (0.25 + 0.75 * abs(math.sin(i * 0.7 + rng.uniform(0, 1)))) * size * 0.28
        x0 = 32 + i * (size - 64) / bars
        d.rounded_rectangle([x0, size - 40 - h, x0 + (size - 64) / bars * 0.6, size - 40], radius=4,
                            fill=(255, 255, 255, 150))
    over = over.filter(ImageFilter.GaussianBlur(0.6))
    im = Image.alpha_composite(im.convert("RGBA"), over).convert("RGB")
    im.save(path, "WEBP", quality=82, method=6)


def dump_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def build_pack(g: Genre, seed: int) -> Path:
    print(f"[{g.id}] synthesising…", flush=True)
    b = PackBuilder(g, seed)
    b.build_loops()
    b.build_shots()
    b.build_sequences()

    out = ASSETS / g.id
    if out.exists():
        shutil.rmtree(out)
    (out / "samples").mkdir(parents=True)

    for name, audio in b.audio.items():
        write_ogg(out / "samples" / f"{name}.ogg", audio)
    for name, meta in b.sample_meta.items():
        dump_json(out / "samples" / f"{name}.json", meta)
    for name, text in b.drums.items():
        (out / "samples" / f"{name}.drum").write_text(text + "\n", encoding="utf-8")
    dump_json(out / "samples" / "Song_8x6.song", b.song())
    write_ogg(out / "preview.ogg", b.preview())
    write_cover(out / "cover.webp", g, seed)

    peaks = [float(np.max(np.abs(a))) for a in b.audio.values()]
    rms = [float(np.sqrt(np.mean(a ** 2))) for a in b.audio.values() if a.shape[0] > SR]
    dump_json(out / "default.json", {
        "name": g.name, "productId": g.id, "version": GENERATOR_VERSION, "author": "Draw Music",
        "copyright": "Draw Music — generated by tools/beatpack-gen", "short_description": g.description,
        "long_description": f"{g.genre} pack in {g.key} at {g.bpm:g} BPM: 48 loops, 48 one-shots and 48 sequences.",
        "bpm": float(g.bpm), "key": g.key, "quantize": 4.0, "drumQuantize": 0.25, "sessions": ["8x6.json"],
        "loudness": round(20 * math.log10(float(np.mean(rms)) + 1e-9), 2),
        "peak": round(max(peaks), 3), "genre": g.genre, "isPremium": False,
    })
    dump_json(out / "8x6.json", b.session())
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"[{g.id}] {len(b.audio)} audio, {len(b.drums)} sequences, {size / 1e6:.2f} MB", flush=True)
    return out


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str]) -> None:
    wanted = set(argv) or {g.id for g in PACKS}
    unknown = wanted - {g.id for g in PACKS}
    if unknown:
        sys.exit(f"Unknown pack id(s): {', '.join(sorted(unknown))}")
    ASSETS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": {}}
    for seed, g in enumerate(PACKS):
        if g.id not in wanted:
            continue
        out = build_pack(g, 1000 + seed * 17)
        manifest["files"] = {k: v for k, v in manifest["files"].items() if not k.startswith(f"{g.id}/")}
        for f in sorted(out.rglob("*")):
            if f.is_file():
                rel = f.relative_to(ASSETS).as_posix()
                manifest["files"][rel] = {"source": "generated", "generator": f"beatpack_gen.py {GENERATOR_VERSION}",
                                          "sha256": sha256(f)}
    index = {"version": 1, "packs": [g.id for g in PACKS]}
    dump_json(ASSETS / "index.json", index)
    manifest["files"]["index.json"] = {"source": "generated", "generator": f"beatpack_gen.py {GENERATOR_VERSION}",
                                       "sha256": sha256(ASSETS / "index.json")}
    manifest["files"] = dict(sorted(manifest["files"].items()))
    manifest["generator"] = GENERATOR_VERSION
    MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"manifest: {len(manifest['files'])} files")


if __name__ == "__main__":
    main(sys.argv[1:])
