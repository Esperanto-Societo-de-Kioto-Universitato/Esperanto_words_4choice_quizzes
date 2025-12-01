import argparse
from pathlib import Path

import pandas as pd

import vocab_grouping as vg
from generate_audio_batch import clean_word, synthesize_rhvoice


def find_missing(csv_path: Path, audio_dir: Path):
    df = pd.read_csv(csv_path)
    missing = []
    for row in df.itertuples():
        original = str(row.Esperanto).strip()
        if not original:
            continue
        key = vg._default_audio_key(original)
        if not any((audio_dir / f"{key}{ext}").exists() for ext in [".wav", ".mp3", ".ogg"]):
            missing.append((original, key))
    return missing


def main():
    parser = argparse.ArgumentParser(description="音声ファイルの欠損を洗い出し、任意で再生成します。")
parser.add_argument("--csv", type=Path, default=Path("2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv"))
    parser.add_argument("--audio-dir", type=Path, default=Path("audio"))
    parser.add_argument("--voice", type=str, default="spomenka")
    parser.add_argument("--regen", action="store_true", help="欠損分をRHVoiceで生成する")
    parser.add_argument("--no-clean", action="store_true", help="単語クリーンを無効化して生成")
    args = parser.parse_args()

    args.audio_dir.mkdir(parents=True, exist_ok=True)
    missing = find_missing(args.csv, args.audio_dir)
    if not missing:
        print("欠損なし")
        return

    print(f"欠損 {len(missing)} 件:")
    for orig, key in missing:
        print(f"- {orig} -> {key}.wav")

    if args.regen:
        ok = 0
        ng = 0
        for orig, key in missing:
            word = orig if args.no_clean else clean_word(orig)
            out_path = args.audio_dir / f"{key}.wav"
            if synthesize_rhvoice(word, out_path, args.voice):
                ok += 1
            else:
                ng += 1
        print(f"再生成完了: 成功 {ok}, 失敗 {ng}")


if __name__ == "__main__":
    main()
