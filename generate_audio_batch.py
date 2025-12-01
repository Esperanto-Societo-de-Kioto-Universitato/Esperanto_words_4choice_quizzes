import argparse
import re
import subprocess
from pathlib import Path

import pandas as pd

import vocab_grouping as vg


def clean_word(raw: str) -> str:
    """
    RHVoice が読みにくい装飾を取り除く。
    - 先頭末尾のハイフンやスラッシュ・括弧内説明などを除去
    - 空になった場合は元を返す
    """
    w = raw.strip()
    # remove bracketed notes like (sin)
    w = re.sub(r"\\(.*?\\)", "", w)
    # drop leading/trailing punctuation/hyphen/slash
    w = w.strip("-/ ")
    # collapse multiple spaces
    w = re.sub(r"\\s+", " ", w)
    return w or raw


def synthesize_rhvoice(text: str, out_path: Path, voice: str) -> bool:
    try:
        result = subprocess.run(
            ["RHVoice-test", "-p", voice, "-o", str(out_path)],
            input=text.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        print("RHVoice-test が見つかりません。`sudo apt install rhvoice` 等で導入してください。")
        return False
    except subprocess.CalledProcessError as e:
        print(f"生成失敗: {text} -> {out_path.name}")
        print(e.stderr.decode("utf-8", errors="ignore"))
        return False


def main():
    parser = argparse.ArgumentParser(description="RHVoice で語彙の音声を一括生成します。")
parser.add_argument("--csv", type=Path, default=Path("2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv"))
    parser.add_argument("--out", type=Path, default=Path("audio"), help="出力ディレクトリ (.wav)")
    parser.add_argument("--voice", type=str, default="spomenka", help="RHVoice の音声名")
    parser.add_argument("--skip-existing", action="store_true", help="既存ファイルはスキップ")
    parser.add_argument("--limit", type=int, help="生成上限（テスト用）")
    parser.add_argument("--no-clean", action="store_true", help="単語のハイフン等の簡易クリーンを無効化")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    args.out.mkdir(parents=True, exist_ok=True)

    rows = df.itertuples()
    if args.limit:
        rows = list(rows)[: args.limit]

    ok = 0
    ng = 0
    for row in rows:
        original = str(row.Esperanto).strip()
        word = original if args.no_clean else clean_word(original)
        if not word:
            continue
        key = vg._default_audio_key(original)
        out_path = args.out / f"{key}.wav"
        if args.skip_existing and out_path.exists():
            continue
        if synthesize_rhvoice(word, out_path, args.voice):
            ok += 1
        else:
            ng += 1

    print(f"完了: 成功 {ok}, 失敗 {ng}")


if __name__ == "__main__":
    main()
