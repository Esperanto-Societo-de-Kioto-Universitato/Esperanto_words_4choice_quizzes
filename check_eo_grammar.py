import pandas as pd
import re
from pathlib import Path

csv_path = Path("phrases_eo_en_ja_zh_ko_ru_fulfilled_251130.csv")
df = pd.read_csv(csv_path)

grammar_issues = []

# Helper prepositions that NEVER take the accusative
no_acc_preps = ["al", "de", "el", "kun", "per", "pro", "pri", "por", "sen", "laŭ", "krom"]

def check_sentence(idx, eo, ja):
    issues = []
    words = re.findall(r'\b[a-zA-ZĉĝĥĵŝŭĈĜĤĴŜŬ]+\b', eo.lower())
    
    for i, w in enumerate(words):
        # 1. Preposition + Accusative check (basic)
        if w in no_acc_preps and i + 1 < len(words):
            next_w = words[i+1]
            if next_w not in ["la", "mia", "via", "lia", "ŝia", "ĝia", "nia", "ilia", "sia"]:
                if next_w.endswith("n") and next_w != "n" and next_w != "un":  # basic check
                    # wait, adverbs can end in 'n' (e.g., matenen)? But "de lundon" is wrong.
                    # let's only flag adjectives/nouns ending in 'on', 'an', 'ojn', 'ajn'
                    if next_w.endswith("on") or next_w.endswith("an") or next_w.endswith("ojn") or next_w.endswith("ajn") or next_w in ["min", "vin", "lin", "ŝin", "ĝin", "nin", "ilin", "sin", "kiun", "tiun", "iun", "neniun", "ĉiun"]:
                        issues.append(f"Preposition '{w}' with accusative '{next_w}'")
            elif i + 2 < len(words):
                next_next_w = words[i+2]
                if next_next_w.endswith("on") or next_next_w.endswith("an") or next_next_w.endswith("ojn") or next_next_w.endswith("ajn"):
                    issues.append(f"Preposition '{w}' with accusative '{next_next_w}'")

        # 2. Adjective - Noun agreement check (basic adjacent pairs)
        if w.endswith("a") and i + 1 < len(words):
            next_w = words[i+1]
            if next_w.endswith("oj") or next_w.endswith("ojn") or next_w.endswith("on"):
                issues.append(f"Adj/Noun mismatch: '{w}' and '{next_w}'")
        
        if w.endswith("aj") and i + 1 < len(words):
            next_w = words[i+1]
            if next_w.endswith("o") or next_w.endswith("on") or next_w.endswith("ojn"):
                if not (next_w in ["do", "pro"]): # ignore simple words
                    issues.append(f"Adj/Noun mismatch: '{w}' and '{next_w}'")
                    
        if w.endswith("an") and i + 1 < len(words):
            next_w = words[i+1]
            if next_w.endswith("o") or next_w.endswith("oj") or next_w.endswith("ojn"):
                issues.append(f"Adj/Noun mismatch: '{w}' and '{next_w}'")
                
        if w.endswith("ajn") and i + 1 < len(words):
            next_w = words[i+1]
            if next_w.endswith("o") or next_w.endswith("oj") or next_w.endswith("on"):
                issues.append(f"Adj/Noun mismatch: '{w}' and '{next_w}'")
                
        # 3. da + accusative
        if w == "da" and i + 1 < len(words):
            next_w = words[i+1]
            if next_w.endswith("n"):
                issues.append(f"'da' with accusative '{next_w}'")

    if issues:
        grammar_issues.append((idx, eo, ja, list(set(issues))))

for idx, row in df.iterrows():
    if pd.notna(row['Esperanto']):
        check_sentence(int(row['PhraseID']), row['Esperanto'], row['日本語'])

print(f"Found {len(grammar_issues)} potentially problematic sentences.")
for item in grammar_issues[:50]:
    print(f"ID {item[0]}: {item[1]} ({item[2]}) -> {item[3]}")

