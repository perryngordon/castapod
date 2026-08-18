#!/usr/bin/env python3
"""Render a chapter-marked script.md into a single narrated episode WAV + chapters.json.

script.md format: `# Title` then one or more `## Chapter Name` sections, each followed
by the chapter's narration text (plain paragraphs).
"""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load

MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
SPEAKER = "Aiden"
INSTRUCT = (
    "Energetic, natural podcast host voice. Normal conversational speaking pace, "
    "clear and lively, with brief natural pauses only between sentences."
)
SAMPLE_RATE = 24000
CHAPTER_GAP_SECONDS = 0.9


def parse_chapters(script_path: Path):
    text = script_path.read_text(encoding="utf-8")
    parts = re.split(r"^##\s+(.+)$", text, flags=re.MULTILINE)
    # parts[0] is preamble (title etc.), then alternating [name, body, name, body, ...]
    chapters = []
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        body = " ".join(parts[i + 1].split())
        if body:
            chapters.append((name, body))
    return chapters


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--speaker", default=SPEAKER)
    parser.add_argument("--instruct", default=INSTRUCT)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    chapters = parse_chapters(args.script)
    if not chapters:
        raise SystemExit(f"No '## Chapter' sections found in {args.script}")

    print(f"Loading {MODEL_ID} ...")
    model = load(MODEL_ID)

    gap = np.zeros(int(CHAPTER_GAP_SECONDS * SAMPLE_RATE), dtype=np.float32)
    full_audio = []
    chapter_marks = []
    cursor = 0.0

    for name, body in chapters:
        print(f"Rendering chapter: {name} ({len(body)} chars)")
        results = list(
            model.generate_custom_voice(
                text=body,
                speaker=args.speaker,
                language="English",
                instruct=args.instruct,
            )
        )
        audio = np.array(results[0].audio, dtype=np.float32)
        chapter_marks.append({"title": name, "start_seconds": round(cursor, 2)})
        full_audio.append(audio)
        cursor += len(audio) / SAMPLE_RATE
        full_audio.append(gap)
        cursor += CHAPTER_GAP_SECONDS

    joined = np.concatenate(full_audio)
    out_wav = args.out_dir / "episode.wav"
    sf.write(out_wav, joined, SAMPLE_RATE)

    out_json = args.out_dir / "chapters.json"
    out_json.write_text(json.dumps(chapter_marks, indent=2))

    print(f"Wrote {out_wav} ({len(joined)/SAMPLE_RATE:.1f}s total)")
    print(f"Wrote {out_json}")


if __name__ == "__main__":
    main()
