#!/usr/bin/env python3
"""Local CLI TTS wrapper around Qwen3-TTS-12Hz (mlx-audio), for OpenClaw's tts-local-cli provider."""

import argparse

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--speaker", default=SPEAKER)
    parser.add_argument("--instruct", default=INSTRUCT)
    parser.add_argument("--language", default="English")
    args = parser.parse_args()

    model = load(MODEL_ID)
    results = list(
        model.generate_custom_voice(
            text=args.text,
            speaker=args.speaker,
            language=args.language,
            instruct=args.instruct,
        )
    )
    audio = np.array(results[0].audio)
    sf.write(args.output, audio, SAMPLE_RATE)


if __name__ == "__main__":
    main()
