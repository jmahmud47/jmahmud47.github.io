#!/usr/bin/env python3
"""Render narrated, animated AI-summary videos for the publications page.

Each paper's narration lives in papers.json, keyed by its BibTeX key. The
videos and poster images are written to assets/video/ai-summaries/.

Requires macOS (`say`, `afconvert`), Pillow, and imageio-ffmpeg:

    pip install pillow imageio-ffmpeg
    python3 _scripts/ai-summaries/make_videos.py              # every paper
    python3 _scripts/ai-summaries/make_videos.py Baral2024    # selected keys
"""

import argparse
import functools
import json
import math
import os
import random
import re
import subprocess
import tempfile
import wave
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
LOGOS = REPO / "assets" / "img" / "publication_preview"
OUT = REPO / "assets" / "video" / "ai-summaries"

W, H, FPS = 1280, 720, 24
VOICE, RATE, SR = "Samantha", 172, 22050
LEAD_IN, GAP, TAIL = 0.6, 0.55, 1.6
XFADE = 0.5  # crossfade between slides, seconds
MARGIN = 110
SITE = "jmahmud47.github.io"

ACCENT = (181, 9, 172)  # site theme purple (#b509ac)
TEAL = (60, 200, 200)
ORANGE = (255, 154, 60)
INDIGO = (106, 92, 255)
WHITE = (255, 255, 255)
SOFT = (190, 196, 222)

try:
    import imageio_ffmpeg

    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG = "ffmpeg"

# Spoken forms for acronyms and tool names the system voice mispronounces
SAY_FIXES = [
    (r"\s*\((?:APR|LLMs?|GUIs?|UIs?)\)", ""),
    (r"\bUI-centric\b", "U I centric"),
    (r"\bUI-driven\b", "U I driven"),
    (r"\bGUI-based\b", "G U I based"),
    (r"\bGUI-related\b", "G U I related"),
    (r"\bGUIs\b", "G U Is"),
    (r"\bGUI\b", "G U I"),
    (r"\bUIs\b", "U Is"),
    (r"\bUI\b", "U I"),
    (r"\bLLM-based\b", "L L M based"),
    (r"\bLLMs\b", "L L Ms"),
    (r"\bLLM\b", "L L M"),
    (r"\bAPR\b", "A P R"),
    (r"Hits@10", "hits at ten"),
    (r"\bF1\b", "F 1"),
    (r"MDroid\+", "M Droid plus"),
    (r"\bAndroB2O\b", "Andro B 2 O"),
    (r"\bAndroR2\b", "Andro R 2"),
    (r"\bAstroBR\b", "Astro B R"),
    (r"\bLadyBug\b", "Lady Bug"),
    (r"\bRedWing\b", "Red Wing"),
    (r"\bReBL\b", "Re B L"),
    (r"\bDroidFixBench\b", "Droid Fix Bench"),
    (r"\bOpenHands\b", "Open Hands"),
    (r"\bMAES\b", "M A E S"),
    (r"\bAES\b", "A E S"),
    (r"\bAPK\b", "A P K"),
    (r"\bIoT\b", "I o T"),
    (r"BLEU-4", "BLEU 4"),
    (r"ROUGE-L", "ROUGE L"),
    (r"\bBURT\b", "Burt"),
    (r"\s*[—–]\s*", ", "),
    (r"&", "and"),
]


def spoken(text):
    for pattern, replacement in SAY_FIXES:
        text = re.sub(pattern, replacement, text)
    return text


@functools.lru_cache(maxsize=None)
def font(style, size):
    path = "/System/Library/Fonts/Avenir Next.ttc"
    if os.path.exists(path):
        for index in range(24):
            try:
                face = ImageFont.truetype(path, size, index=index)
            except OSError:
                break
            if face.getname()[1] == style:
                return face
    name = "Arial.ttf" if style in ("Regular", "Medium") else "Arial Bold.ttf"
    return ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{name}", size)


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ease_out(x):
    return 1 - (1 - clamp(x)) ** 3


def ease_out_back(x):
    x = clamp(x)
    return 1 + 2.70158 * (x - 1) ** 3 + 1.70158 * (x - 1) ** 2


def with_alpha(img, a):
    """Scale an RGBA image's opacity by a (0..1)."""
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return out


def paste(frame, img, xy, a=1.0):
    if a <= 0.001:
        return
    img = with_alpha(img, a)
    frame.paste(img, (int(xy[0]), int(xy[1])), img)


# --------------------------------------------------------------------------- #
# Static artwork
# --------------------------------------------------------------------------- #


def make_background():
    top, bottom = (9, 11, 30), (30, 9, 46)
    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        f = y / (H - 1)
        draw.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * f) for a, b in zip(top, bottom)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((-260, -320, 620, 420), fill=ACCENT + (70,))
    gdraw.ellipse((780, 380, 1560, 1060), fill=TEAL + (45,))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    return Image.alpha_composite(bg.convert("RGBA"), glow).convert("RGB")


def make_bokeh(seed):
    rnd = random.Random(seed)
    sprites = []
    for _ in range(9):
        r = rnd.randint(40, 130)
        pad = r // 2 + 10
        size = 2 * (r + pad)
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        color = rnd.choice([ACCENT, TEAL, ORANGE, INDIGO])
        ImageDraw.Draw(img).ellipse((pad, pad, pad + 2 * r, pad + 2 * r), fill=color + (rnd.randint(28, 60),))
        sprites.append(
            dict(
                img=img.filter(ImageFilter.GaussianBlur(r / 3)),
                half=size // 2,
                cx=rnd.uniform(0, W),
                cy=rnd.uniform(0, H),
                ax=rnd.uniform(40, 120),
                ay=rnd.uniform(30, 90),
                px=rnd.uniform(18, 36),
                py=rnd.uniform(16, 32),
                ph=rnd.uniform(0, 2 * math.pi),
            )
        )
    return sprites


def gradient_strip(w, h, stops=(ACCENT, ORANGE, TEAL, INDIGO)):
    strip = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(strip)
    for x in range(w):
        f = x / max(1, w - 1) * (len(stops) - 1)
        i = min(int(f), len(stops) - 2)
        k = f - i
        color = tuple(int(stops[i][j] + (stops[i + 1][j] - stops[i][j]) * k) for j in range(3))
        draw.line([(x, 0), (x, h)], fill=color + (255,))
    return strip


def logo_card(logo_file, w, h, border=4, radius=16):
    """White rounded card with the venue logo and a gradient border, plus a soft shadow."""
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=255)
    card.paste(gradient_strip(w, h), (0, 0), mask)
    ImageDraw.Draw(card).rounded_rectangle((border, border, w - 1 - border, h - 1 - border), radius - border, fill=WHITE + (255,))
    logo = Image.open(LOGOS / logo_file).convert("RGBA")
    pad = border + max(6, h // 14)
    logo.thumbnail((w - 2 * pad, h - 2 * pad), Image.LANCZOS)
    card.alpha_composite(logo, ((w - logo.width) // 2, (h - logo.height) // 2))

    s = 24
    shadow = Image.new("RGBA", (w + 2 * s, h + 2 * s), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((s, s + 8, s + w, s + h + 8), radius, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    shadow.alpha_composite(card, (s, s))
    return shadow, s


def wrap(text, face, max_w):
    lines, cur = [], []
    for word in text.split():
        if cur and face.getlength(" ".join(cur + [word])) > max_w:
            lines.append(cur)
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(cur)
    return lines


def text_block(text, face, max_w, line_h, fill, align="left", max_lines=None):
    lines = wrap(text, face, max_w)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and face.getlength(" ".join(lines[-1] + ["…"])) > max_w:
            lines[-1].pop()
        lines[-1].append("…")
    img = Image.new("RGBA", (max_w, line_h * len(lines) + 14), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        s = " ".join(line)
        x = (max_w - face.getlength(s)) / 2 if align == "center" else 0
        draw.text((x, i * line_h), s, font=face, fill=fill)
    return img


def reveal_block(text, face, max_w, line_h):
    """Body text rendered twice (dim + bright) with per-word boxes for karaoke-style reveal."""
    lines = wrap(text, face, max_w)
    size = (max_w, line_h * len(lines) + 14)
    bright = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(bright)
    space = face.getlength(" ")
    boxes = []
    for i, line in enumerate(lines):
        x, y = 0.0, i * line_h
        for word in line:
            draw.text((x, y), word, font=face, fill=WHITE + (255,))
            wl = face.getlength(word)
            boxes.append((int(x) - 2, y - 6, int(x + wl + space) + 2, y + line_h))
            x += wl + space
    dim = with_alpha(bright, 0.28)
    return dim, bright, boxes


def pill(text, face, color):
    tw = int(face.getlength(text))
    img = Image.new("RGBA", (tw + 36, 34), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, tw + 35, 33), 17, outline=color + (255,), width=2, fill=color + (40,))
    draw.text((18, 7), text, font=face, fill=WHITE + (255,))
    return img


# --------------------------------------------------------------------------- #
# Slides
# --------------------------------------------------------------------------- #


class Video:
    def __init__(self, key, paper):
        self.key, self.p = key, paper
        self.bg = make_background()
        self.bokeh = make_bokeh(key)
        self.bar = gradient_strip(W, 5)
        self.big_card, self.big_pad = logo_card(paper["logo"], 320, 180)
        self.small_card, self.small_pad = logo_card(paper["logo"], 112, 63, border=3, radius=10)
        self.end_card, self.end_pad = logo_card(paper["logo"], 240, 135)
        self.cache = {}
        self._build_title()
        self._build_header()
        self._build_outro()

    def _build_title(self):
        p = self.p
        title_face = font("Demi Bold", 44)
        self.t_title = text_block(p["title"], title_face, 1060, 56, WHITE, "center", 3)
        self.t_auth = text_block(p["authors"], font("Regular", 24), 1000, 32, SOFT, "center", 2)
        self.t_venue = text_block(p["venue"], font("Demi Bold", 28), 1000, 36, TEAL, "center", 1)
        self.t_pill = pill("AI-GENERATED SUMMARY", font("Demi Bold", 15), ACCENT)
        card_h = self.big_card.height - 2 * self.big_pad
        heights = [card_h, 34, self.t_title.height, 10, self.t_auth.height, 8, self.t_venue.height, 18, self.t_pill.height]
        self.title_y0 = (H - sum(heights)) / 2 - 6

    def _build_header(self):
        self.h_venue = text_block(self.p["venue"], font("Demi Bold", 22), 900, 28, TEAL, max_lines=1)
        self.h_title = text_block(self.p["title"], font("Regular", 18), 960, 24, SOFT, max_lines=1)
        mark = f"AI-generated summary · {SITE}"
        self.watermark = text_block(mark, font("Medium", 17), 600, 22, SOFT + (170,))
        self.mark_w = font("Medium", 17).getlength(mark)

    def _build_outro(self):
        self.o_read = text_block("Read the full paper", font("Demi Bold", 54), 1000, 64, WHITE, "center", 1)
        self.o_url = text_block(f"{SITE}/publications", font("Demi Bold", 32), 1000, 40, TEAL, "center", 1)
        source = "the paper" if self.p.get("source") == "paper" else "the paper's abstract"
        note = f"AI-generated summary: narration and visuals were generated with AI from {source}."
        self.o_note = text_block(note, font("Regular", 20), 1100, 26, SOFT, "center", 2)

    def content(self, seg):
        """Pre-rendered layers for a content slide."""
        if id(seg) not in self.cache:
            head = text_block(seg["head"], font("Demi Bold", 48), 1060, 58, WHITE, max_lines=2)
            dim, bright, boxes = reveal_block(seg["text"], font("Regular", 33), 1060, 47)
            self.cache[id(seg)] = dict(head=head, dim=dim, bright=bright, boxes=boxes, reveal={})
        return self.cache[id(seg)]

    def revealed(self, layers, k):
        if k not in layers["reveal"]:
            mask = Image.new("L", layers["bright"].size, 0)
            draw = ImageDraw.Draw(mask)
            for box in layers["boxes"][:k]:
                draw.rectangle(box, fill=255)
            img = layers["bright"].copy()
            img.putalpha(ImageChops.multiply(layers["bright"].getchannel("A"), mask))
            layers["reveal"][k] = img
        return layers["reveal"][k]

    # -- slide renderers ---------------------------------------------------- #

    def base(self, t):
        frame = self.bg.copy()
        for s in self.bokeh:
            x = s["cx"] + s["ax"] * math.sin(2 * math.pi * t / s["px"] + s["ph"])
            y = s["cy"] + s["ay"] * math.cos(2 * math.pi * t / s["py"] + s["ph"])
            frame.paste(s["img"], (int(x) - s["half"], int(y) - s["half"]), s["img"])
        return frame

    def draw_title(self, frame, lt):
        y = self.title_y0
        a = ease_out(lt / 0.6)
        scale = 0.86 + 0.14 * ease_out_back(lt / 0.7)
        card = self.big_card
        if scale < 0.999:
            card = card.resize((int(card.width * scale), int(card.height * scale)), Image.LANCZOS)
        card_h = self.big_card.height - 2 * self.big_pad
        cy = y + card_h / 2
        paste(frame, card, ((W - card.width) / 2, cy - card.height / 2 + 4), a)
        y += card_h + 34
        for layer, delay, gap in ((self.t_title, 0.25, 10), (self.t_auth, 0.45, 8), (self.t_venue, 0.6, 18)):
            e = ease_out((lt - delay) / 0.6)
            paste(frame, layer, ((W - layer.width) / 2, y + (1 - e) * 22), e)
            y += layer.height + gap
        e = ease_out((lt - 0.8) / 0.6)
        paste(frame, self.t_pill, ((W - self.t_pill.width) / 2, y + (1 - e) * 16), e)

    def draw_header(self, frame):
        paste(frame, self.small_card, (MARGIN - self.small_pad, 34 - self.small_pad))
        paste(frame, self.h_venue, (MARGIN + 130, 40))
        paste(frame, self.h_title, (MARGIN + 130, 72))

    def draw_content(self, frame, seg, idx, count, lt):
        layers = self.content(seg)
        self.draw_header(frame)
        step = text_block(f"{idx:02d} / {count:02d}", font("Demi Bold", 20), 300, 26, TEAL, max_lines=1)
        paste(frame, step, (MARGIN, 168))
        e = ease_out(lt / 0.6)
        head_y = 200
        paste(frame, layers["head"], (MARGIN - (1 - e) * 30, head_y), max(e, 0.35))
        body_y = head_y + layers["head"].height + 14
        paste(frame, layers["dim"], (MARGIN, body_y))
        progress = clamp((lt - 0.1) / max(0.5, seg["speech"] * 0.93))
        k = math.ceil(progress * len(layers["boxes"]))
        if k:
            paste(frame, self.revealed(layers, k), (MARGIN, body_y))
        bar_h = int((body_y + layers["dim"].height - head_y - 14) * ease_out(lt / 0.8))
        if bar_h > 0:
            accent = gradient_strip(bar_h, 6, (ACCENT, ORANGE, TEAL)).rotate(90, expand=True)
            frame.paste(accent, (MARGIN - 30, head_y + 6), accent)
        paste(frame, self.watermark, (W - MARGIN - self.mark_w, H - 44))

    def draw_outro(self, frame, lt, t):
        float_y = 4 * math.sin(t * 1.6)
        card = self.end_card
        paste(frame, card, ((W - card.width) / 2, 110 - self.end_pad + float_y))
        y = 110 + card.height - 2 * self.end_pad + 46
        for layer, delay, gap in ((self.o_read, 0.1, 16), (self.o_url, 0.3, 0)):
            e = ease_out((lt - delay) / 0.6)
            paste(frame, layer, ((W - layer.width) / 2, y + (1 - e) * 20), e)
            y += layer.height + gap
        paste(frame, self.o_note, ((W - self.o_note.width) / 2, H - 120), ease_out((lt - 0.5) / 0.8))

    def slide(self, i, lt, t):
        seg = self.segs[i]
        frame = self.base(t)
        if seg["kind"] == "title":
            self.draw_title(frame, lt)
        elif seg["kind"] == "outro":
            self.draw_outro(frame, lt, t)
        else:
            self.draw_content(frame, seg, seg["idx"], self.n_content, lt)
        return frame

    # -- audio + timeline ---------------------------------------------------- #

    def narrate(self, work):
        p = self.p
        intro = f"This is an AI-generated summary of the paper: {p['title']}. By {p['lead']}. Published at {p['venue_say']}."
        items = [dict(kind="title", say=intro)]
        for n, s in enumerate(p["segments"], 1):
            items.append(dict(kind="content", idx=n, head=s["head"], text=s["text"], say=s.get("say", s["text"])))
        items.append(dict(kind="outro", say="To learn more, read the full paper on Junayed Mahmud's publications page."))
        self.n_content = len(p["segments"])

        pcm = bytearray(b"\x00\x00" * int(SR * LEAD_IN))
        for n, item in enumerate(items):
            aiff, wav = work / f"seg{n}.aiff", work / f"seg{n}.wav"
            subprocess.run(["say", "-v", VOICE, "-r", str(RATE), "-o", str(aiff), spoken(item["say"])], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{SR}", "-c", "1", str(aiff), str(wav)], check=True)
            with wave.open(str(wav)) as w:
                data = w.readframes(w.getnframes())
            item["start"] = len(pcm) / 2 / SR
            item["speech"] = len(data) / 2 / SR
            pcm += data
            pcm += b"\x00\x00" * int(SR * (TAIL if n == len(items) - 1 else GAP))
        self.segs = items
        self.duration = len(pcm) / 2 / SR
        for n, item in enumerate(items):
            item["win"] = 0.0 if n == 0 else item["start"]
        audio = work / "narration.wav"
        with wave.open(str(audio), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(bytes(pcm))
        return audio

    def frame_at(self, t):
        i = max(n for n, s in enumerate(self.segs) if s["win"] <= t)
        lt = t - self.segs[i]["win"]
        frame = self.slide(i, lt, t)
        if i > 0 and lt < XFADE:
            prev = self.segs[i - 1]
            frame = Image.blend(self.slide(i - 1, self.segs[i]["win"] - prev["win"], t), frame, ease_out(lt / XFADE))
        fill = int(W * t / self.duration)
        frame.paste((20, 20, 40), (0, H - 5, W, H))
        if fill > 0:
            frame.paste(self.bar.crop((0, 0, fill, 5)), (0, H - 5))
        return frame

    def render(self, mp4, poster, work):
        audio = self.narrate(work)
        self.frame_at(min(2.6, self.segs[1]["win"] - 0.1)).save(poster, quality=92)
        cmd = [
            FFMPEG, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-i", str(audio),
            "-c:v", "libx264", "-preset", "medium", "-crf", "27", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "80k", "-shortest", "-movflags", "+faststart", str(mp4),
        ]  # fmt: skip
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        frames = math.ceil(self.duration * FPS)
        for f in range(frames):
            proc.stdin.write(self.frame_at(f / FPS).tobytes())
        proc.stdin.close()
        if proc.wait():
            raise RuntimeError(f"ffmpeg failed for {self.key}")
        return self.duration, frames


def render_one(key, paper):
    OUT.mkdir(parents=True, exist_ok=True)
    mp4, poster = OUT / f"{paper['slug']}.mp4", OUT / f"{paper['slug']}.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        duration, frames = Video(key, paper).render(mp4, poster, Path(tmp))
    return key, paper["slug"], duration, frames, mp4.stat().st_size


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("keys", nargs="*", help="BibTeX keys to render (default: all)")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    papers = json.loads((HERE / "papers.json").read_text())
    keys = args.keys or list(papers)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(render_one, k, papers[k]): k for k in keys}
        for fut in as_completed(futures):
            try:
                key, slug, duration, frames, size = fut.result()
                print(f"ok   {key:24} {slug}.mp4  {duration:5.1f}s  {frames} frames  {size / 1e6:.1f} MB", flush=True)
            except Exception as exc:  # keep rendering the others
                print(f"FAIL {futures[fut]:24} {exc}", flush=True)


if __name__ == "__main__":
    main()
