import csv
import re
import sys

csv_path = "phrases_eo_en_ja_zh_ko_ru_fulfilled_251130.csv"

grammar_issues = []
no_acc_preps = ["al", "de", "el", "kun", "per", "pro", "pri", "por", "sen", "laŭ", "krom"]

try:
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = row.get('PhraseID')
            eo = row.get('Esperanto')
            ja = row.get('日本語')
            
            if not eo:
                continue
                
            issues = []
            words = re.findall(r'\b[a-zA-ZĉĝĥĵŝŭĈĜĤĴŜŬ]+\b', eo.lower())
            
            for i, w in enumerate(words):
                # 1. Preposition + Accusative check
                if w in no_acc_preps and i + 1 < len(words):
                    next_w = words[i+1]
                    if next_w not in ["la", "mia", "via", "lia", "ŝia", "ĝia", "nia", "ilia", "sia"]:
                        if next_w.endswith("on") or next_w.endswith("an") or next_w.endswith("ojn") or next_w.endswith("ajn") or next_w in ["min", "vin", "lin", "ŝin", "ĝin", "nin", "ilin", "sin", "kiun", "tiun", "iun"]:
                            issues.append(f"Preposition '{w}' + acc '{next_w}'")
                    elif i + 2 < len(words):
                        next_next_w = words[i+2]
                        if next_next_w.endswith("on") or next_next_w.endswith("an") or next_next_w.endswith("ojn") or next_next_w.endswith("ajn") or next_next_w in ["min", "vin", "lin", "ŝin", "ĝin", "nin", "ilin", "sin", "kiun", "tiun", "iun"]:
                            issues.append(f"Preposition '{w}' + acc '{next_next_w}'")

                # 2. Adjective - Noun agreement check (basic)
                if w.endswith("a") and i + 1 < len(words):
                    next_w = words[i+1]
                    if next_w.endswith("oj") or next_w.endswith("ojn") or next_w.endswith("on"):
                        if next_w not in ["do"]:
                            issues.append(f"Adj/Noun mismatch: '{w}' and '{next_w}'")
                if w.endswith("aj") and i + 1 < len(words):
                    next_w = words[i+1]
                    if next_w.endswith("o") or next_w.endswith("on") or next_w.endswith("ojn"):
                        if next_w not in ["do"]:
                            issues.append(f"Adj/Noun mismatch: '{w}' and '{next_w}'")
                if w.endswith("an") and i + 1 < len(words):
                    next_w = words[i+1]
                    if next_w.endswith("o") or next_w.endswith("oj") or next_w.endswith("ojn"):
                        if next_w not in ["do"]:
                            issues.append(f"Adj/Noun mismatch: '{w}' and '{next_w}'")
                if w.endswith("ajn") and i + 1 < len(words):
                    next_w = words[i+1]
                    if next_w.endswith("o") or next_w.endswith("oj") or next_w.endswith("on"):
                        if next_w not in ["do"]:
                            issues.append(f"Adj/Noun mismatch: '{w}' and '{next_w}'")
                # 3. da + accusative
                if w == "da" and i + 1 < len(words):
                    next_w = words[i+1]
                    if next_w.endswith("n") and next_w not in ["la", "min", "vin", "lin", "ŝin", "ĝin", "nin", "ilin", "sin"]:
                        # "da" shouldn't take accusative anyway, but just basic check
                        if next_w.endswith("on") or next_w.endswith("an") or next_w.endswith("ojn") or next_w.endswith("ajn"):
                            issues.append(f"'da' + acc '{next_w}'")

            if issues:
                grammar_issues.append((idx, eo, ja, list(set(issues))))

    print(f"Found {len(grammar_issues)} potentially problematic sentences.")
    for item in grammar_issues:
        print(f"ID {item[0]}: {item[1]} ({item[2]}) -> {item[3]}")
except Exception as e:
    print(f"Error: {e}")
