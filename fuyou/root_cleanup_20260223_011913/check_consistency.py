import csv
import collections
import re

filepath = 'phrases_eo_en_ja_zh_ko_ru_fulfilled_251130.csv'

with open(filepath, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    rows = list(reader)

issues_overlap = []
issues_punct = []
issues_idiom = []
issues_ai = []

groups = collections.defaultdict(list)

for row in rows:
    if len(row) < 11: continue
    pid = row[0]
    level = row[1]
    topic = row[3]
    subtopic = row[4]
    eo = row[5]
    ja = row[7]
    zh = row[8]
    ko = row[9]
    groups[(level, topic, subtopic)].append((pid, eo, ja, zh, ko))

# 1. Overlap Check
for key, items in groups.items():
    ja_texts = collections.defaultdict(list)
    for it in items:
        norm_ja = re.sub(r'[。！？\?\!\s]', '', it[2])
        ja_texts[norm_ja].append(it)
    
    for norm_ja, items_with_same_ja in ja_texts.items():
        if len(items_with_same_ja) > 1:
            overlap_details = " | ".join([f"[{it[0]}] {it[1]}" for it in items_with_same_ja])
            issues_overlap.append(f"Group {key}: JA='{norm_ja}' matches {len(items_with_same_ja)} phrases:\n    {overlap_details}")

# 2. Punctuation Mismatch
for row in rows:
    if len(row) < 11: continue
    pid, level, level_en, topic, subtopic, eo, en, ja, zh, ko, ru = row
    
    is_q_eo = '?' in eo
    is_q_ja = '？' in ja or '?' in ja or ja.endswith('か。') or ja.endswith('か') or ja.endswith('の。') or ja.endswith('の')
    
    if is_q_eo and not is_q_ja and '!' not in ja:
        if not (ja.endswith('か') or ja.endswith('の') or ja.endswith('ね') or ja.endswith('かしら')):
            issues_punct.append(f"[{pid}] EO is question, JA is not: EO='{eo}' | JA='{ja}'")
            
    if is_q_ja and not is_q_eo:
        if not ('Ĉu' in eo or 'Ki' in eo or 'Bonvolu' in eo or 'Mi petas' in eo):
            issues_punct.append(f"[{pid}] JA is question, EO is not: EO='{eo}' | JA='{ja}'")

# 3. Idiom/Anglicisms
for row in rows:
    if len(row) < 11: continue
    pid, eo, ja = row[0], row[5], row[7]
    eo_lower = eo.lower()
    
    if 'kiel estas via ' in eo_lower and ('kiel estas via nomo' not in eo_lower): 
        # Check context: "Kiel estas via familio" is fine, but "Kiel estas via profesio" is wrong
        issues_idiom.append(f"[{pid}] Possible Anglicism (Kiel vs Kio): '{eo}'")
        
    if 'faras sencon' in eo_lower or 'fari sencon' in eo_lower:
        issues_idiom.append(f"[{pid}] Anglicism: '{eo}' -> better 'havas sencon' or 'estas ŝenca'")
        
    words = set(re.findall(r'\b[a-zĉĝĵŝŭ]+\b', eo_lower))
    if 'ci' in words or 'cin' in words or 'cia' in words or 'cian' in words:
        if 'scias' not in eo_lower:
            issues_idiom.append(f"[{pid}] Archaic 'ci' (thou) used: '{eo}'")

    if 'fartas' in eo_lower and not any(w in ja for w in ['元気', '調子', '気分', 'いかが', 'どう']):
        issues_idiom.append(f"[{pid}] Unusual JA translation for 'fartas': EO='{eo}' | JA='{ja}'")

# 4. Subtle KO Hallucinations
ai_keywords_ko = ['인공지능', '언어 모델', '오픈에이아이', '프로그램']
for row in rows:
    if len(row) < 11: continue
    pid, eo, ko = row[0], row[5], row[9]
    for kw in ai_keywords_ko:
         if kw in ko:
             issues_ai.append(f"[{pid}] Potential KO Hallucination: EO='{eo}' | KO='{ko}'")

print(f"=== OVERVIEW ===")
print(f"1. Quiz Overlaps (Identical JA in same group): {len(issues_overlap)}")
print(f"2. Punctuation Mismatches (?/!): {len(issues_punct)}")
print(f"3. Idiom/Anglicism/Archaic Warnings: {len(issues_idiom)}")
print(f"4. Subtle KO AI Warnings: {len(issues_ai)}\n")

print("--- 1. QUIZ OVERLAPS (Sample) ---")
for i in issues_overlap[:10]: print(i)

print("\n--- 2. PUNCTUATION MISMATCHES (Sample) ---")
for i in issues_punct[:15]: print(i)

print("\n--- 3. IDIOM/ANGLICISM/ARCHAIC WARNINGS ---")
for i in issues_idiom: print(i)

print("\n--- 4. SUBTLE KO AI WARNINGS ---")
for i in issues_ai: print(i)

