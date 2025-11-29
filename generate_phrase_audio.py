import argparse
import re
from pathlib import Path

import pandas as pd

from generate_audio_batch import synthesize_rhvoice
from vocab_grouping import _default_audio_key


DEFAULT_CSV = Path("phrases_en_ru_eo_5000_251129_plejnova.csv")
DEFAULT_OUT_DIR = Path("Esperanto例文5000文_収録音声")
DEFAULT_VOICE = "spomenka"


def clean_sentence(text: str) -> str:
    """
    Make sentences easier for RHVoice to read.
    - Normalize unusual symbols and dashes
    - Expand the degree symbol to a pronounceable form
    - Drop hyphens/underscores that can confuse pronunciation
    """
    cleaned = text.strip()
    cleaned = cleaned.replace("—", " ").replace("–", " ")
    cleaned = cleaned.replace("°C", " gradoj C")
    cleaned = cleaned.replace("°", " gradoj ")
    cleaned = cleaned.replace("_", " ")
    cleaned = cleaned.replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def build_filename(idx: int, esperanto_text: str) -> str:
    """
    Keep filenames predictable and ASCII-only:
    - 1-based, zero-padded index to keep ordering stable
    - x-system transliteration of the original Esperanto text
    - Truncate to avoid excessively long filenames
    """
    slug = _default_audio_key(esperanto_text)
    short_slug = slug[:80].rstrip("_") or "phrase"
    return f"{idx:04d}_{short_slug}.wav"


def main():
    parser = argparse.ArgumentParser(description="Generate RHVoice audio for Esperanto phrases.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Input CSV containing an Esperanto column")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for .wav files")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE, help="RHVoice voice name (e.g. spomenka)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip files that already exist")
    parser.add_argument("--limit", type=int, help="Generate only the first N entries (for testing)")
    parser.add_argument("--start-index", type=int, default=1, help="Start from this 1-based row index")
    parser.add_argument("--no-clean", action="store_true", help="Disable cleaning of sentences before TTS")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    args.out.mkdir(parents=True, exist_ok=True)

    total_rows = len(df)
    print(f"Loaded {total_rows} rows from {args.csv}")

    processed = 0
    generated = 0
    skipped = 0
    failed = 0

    for idx, row in enumerate(df.itertuples(), start=1):
        if idx < args.start_index:
            continue
        if args.limit and processed >= args.limit:
            break

        esperanto = str(row.Esperanto).strip()
        if not esperanto:
            continue

        tts_text = esperanto if args.no_clean else clean_sentence(esperanto)
        filename = build_filename(idx, esperanto)
        out_path = args.out / filename

        if args.skip_existing and out_path.exists():
            skipped += 1
            processed += 1
            continue

        if synthesize_rhvoice(tts_text, out_path, args.voice):
            generated += 1
        else:
            failed += 1

        processed += 1
        if processed % 100 == 0:
            print(
                f"... processed {processed} rows "
                f"(generated={generated}, skipped={skipped}, failed={failed})"
            )

    print(
        f"Done. processed={processed}, generated={generated}, skipped={skipped}, failed={failed}"
    )


if __name__ == "__main__":
    main()
