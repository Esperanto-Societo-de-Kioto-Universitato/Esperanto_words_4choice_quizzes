import csv
import os
import subprocess
import re
from pathlib import Path
from vocab_grouping import _default_audio_key

# --- 設定項目 ---
CSV_FILE_PATH = '2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv'
OUTPUT_DIR = 'audio'
RHVOICE_VOICE = 'spomenka'
AUDIO_EXTENSION = '.wav'
# --- 設定項目ここまで ---

def synthesize_text_with_rhvoice(text, output_filename, voice_name):
    """指定されたテキストからRHVoiceを使用して音声を合成しファイルに保存する"""
    try:
        # テキストからハイフンなどを除去（発音用）
        # ユーザー要望: "-"などを除いた状態で音声化
        safe_text = text.replace('-', ' ').replace('_', ' ')
        
        process = subprocess.run(
            ['RHVoice-test', '-p', voice_name, '-o', output_filename],
            input=safe_text.encode('utf-8'),
            capture_output=True,
            check=True
        )
        # print(f"🎧 Created: {output_filename} (Text: '{safe_text}')")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Error: '{text}' -> RHVoice failed.")
        return False
    except Exception as e:
        print(f"⚠️ Unexpected Error: '{text}' -> {e}")
        return False

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print(f"Reading {CSV_FILE_PATH}...")
    
    try:
        with open(CSV_FILE_PATH, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            total = len(rows)
            
            print(f"Found {total} words. Starting generation...")
            
            count = 0
            updated = 0
            
            for i, row in enumerate(rows):
                word = row.get('Esperanto', '').strip()
                if not word:
                    continue
                
                # Generate filename key using the SAME logic as the app
                key = _default_audio_key(word)
                filename = f"{key}{AUDIO_EXTENSION}"
                output_path = os.path.join(OUTPUT_DIR, filename)
                
                # Always regenerate if it contains hyphen, otherwise check existence
                # User asked to ensure "-" is removed. 
                # To be safe, let's regenerate ALL files that contain hyphens in the source text.
                # For others, we can skip if exists, OR just regenerate all to be sure.
                # Given 3000 words, local TTS is fast (0.1s/word -> 300s = 5 mins).
                # Let's regenerate ONLY if missing OR if source has hyphen.
                
                needs_gen = False
                if not os.path.exists(output_path):
                    needs_gen = True
                elif '-' in word:
                    needs_gen = True # Force regen for hyphens
                
                if needs_gen:
                    if synthesize_text_with_rhvoice(word, output_path, RHVOICE_VOICE):
                        updated += 1
                        if updated % 10 == 0:
                            print(f"Generated {updated} files...", end='\r')
                
                count += 1

            print(f"\nDone! Processed {count} words. Generated/Updated {updated} files.")

    except FileNotFoundError:
        print(f"❌ CSV not found: {CSV_FILE_PATH}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
