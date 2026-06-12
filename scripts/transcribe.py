"""
Extract audio from the downloaded videos and transcribe them to Chinese text
with Whisper (mlx-whisper, Apple-Silicon accelerated).

Pipeline (one file in → one file out, names mirror the source video):

    data/video_download/<channel>/<name>.mp4
        │  ffmpeg  (16kHz mono wav, Whisper-ready)
        ▼
    data/audio/<channel>/<name>.wav
        │  mlx-whisper  (language=zh)  →  raw text
        │  FunASR ct-punc              →  restore 。，？！
        │  split on 。！？             →  one sentence per line
        ▼
    data/transcripts/<channel>/<name>.txt

Whisper is inconsistent about emitting punctuation (some files come out with
none, e.g. fast continuous speakers), so we never rely on its punctuation:
strip it, restore it uniformly with FunASR's Chinese punctuation model, then
split into one sentence per line.

Both steps skip files that already exist, so the script is resumable.

Usage:
    python scripts/transcribe.py [--model ...] [--audio-only]

Requires: ffmpeg (system), mlx-whisper, funasr (venv). Apple Silicon.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import mlx_whisper

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "video_download"
AUDIO_DIR = ROOT / "data" / "audio"
TEXT_DIR = ROOT / "data" / "transcripts"

# large-v3-turbo: best speed/quality balance for Chinese on Apple Silicon.
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
# Nudge Whisper toward Simplified-Chinese Mandarin output.
INITIAL_PROMPT = "以下是普通话的内容，请用简体中文转写。"


def log(msg: str) -> None:
    print(msg, flush=True)


# Sentence-ending punctuation we break lines on (full- and half-width).
SENT_END = "。！？…!?"
# Punctuation/whitespace stripped from Whisper output before re-punctuating,
# so ct-punc sees clean text and every file is punctuated the same way.
PUNCT_STRIP = "，。！？、；：,.!?;:… 　\t"

_punc_model = None


def get_punc_model():
    """Lazily load FunASR's Chinese punctuation-restoration model (ct-punc)."""
    global _punc_model
    if _punc_model is None:
        from funasr import AutoModel
        _punc_model = AutoModel(model="ct-punc", disable_update=True, log_level="ERROR")
    return _punc_model


def restore_punctuation(text: str, chunk: int = 1500) -> str:
    """Strip existing punctuation and re-add it uniformly with ct-punc.

    Processed in fixed-size chunks to bound memory/time on long transcripts.
    """
    clean = "".join(ch for ch in text if ch not in PUNCT_STRIP)
    if not clean:
        return ""
    model = get_punc_model()
    out = []
    for i in range(0, len(clean), chunk):
        out.append(model.generate(input=clean[i:i + chunk])[0]["text"])
    punctuated = "".join(out)
    # ct-punc occasionally inserts a space inside numbers ("2025" → "202 5").
    return re.sub(r"(?<=\d)\s+(?=\d)", "", punctuated)


def split_sentences(text: str) -> list[str]:
    """One sentence per line: break after each sentence-ending mark, keep it."""
    pieces = re.split(rf"(?<=[{SENT_END}])", text)
    return [p.strip() for p in pieces if p.strip()]


def extract_audio(video: Path, audio: Path) -> bool:
    """Extract 16kHz mono wav from a video. Returns True on success."""
    if audio.exists():
        return True
    audio.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(audio),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        log(f"    ✗ ffmpeg failed: {proc.stderr.strip().splitlines()[-1] if proc.stderr else proc.returncode}")
        if audio.exists():
            audio.unlink()  # remove partial
        return False
    return True


def transcribe(audio: Path, text: Path, model: str) -> bool:
    """Transcribe an audio file to a Chinese .txt. Returns True on success."""
    if text.exists():
        return True
    text.parent.mkdir(parents=True, exist_ok=True)
    result = mlx_whisper.transcribe(
        str(audio),
        path_or_hf_repo=model,
        language="zh",
        initial_prompt=INITIAL_PROMPT,
        # Decode each window independently: avoids the runaway repetition loops
        # (e.g. "einfach einfach …") and the punctuation drop-out that context
        # conditioning was causing on some files.
        condition_on_previous_text=False,
        verbose=False,
    )
    # Restore punctuation uniformly, then split into one sentence per line.
    raw = result.get("text", "").strip()
    punctuated = restore_punctuation(raw)
    lines = split_sentences(punctuated) or [raw]
    text.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"mlx-whisper model repo (default {DEFAULT_MODEL})")
    parser.add_argument("--audio-only", action="store_true",
                        help="only extract audio, skip transcription")
    args = parser.parse_args()

    videos = sorted(VIDEO_DIR.rglob("*.mp4"))
    if not videos:
        log(f"No videos found under {VIDEO_DIR}")
        sys.exit(1)

    log(f"Found {len(videos)} videos. Model: {args.model}")
    ok_audio = ok_text = 0

    for i, video in enumerate(videos, 1):
        # Build output names by appending the extension to the FULL stem.
        # (Path.with_suffix would mis-parse the dot in "...ludepress.com】 [id]".)
        channel = video.parent.name
        stem = video.stem  # strips only ".mp4"
        audio = AUDIO_DIR / channel / f"{stem}.wav"
        text = TEXT_DIR / channel / f"{stem}.txt"

        log(f"\n[{i}/{len(videos)}] {channel}/{stem}")

        log("  → extracting audio")
        if not extract_audio(video, audio):
            continue
        ok_audio += 1

        if args.audio_only:
            continue

        log("  → transcribing (zh)")
        try:
            transcribe(audio, text, args.model)
            ok_text += 1
            chars = len(text.read_text(encoding="utf-8"))
            log(f"    ✓ {text.relative_to(ROOT)} ({chars} chars)")
        except Exception as e:  # noqa: BLE001 — keep going on a single failure
            log(f"    ✗ transcription failed: {e}")

    log(f"\n✅ Done. audio: {ok_audio}/{len(videos)}, transcripts: {ok_text}/{len(videos)}")


if __name__ == "__main__":
    main()
