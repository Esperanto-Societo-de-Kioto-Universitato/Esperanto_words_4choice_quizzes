#!/bin/bash
CSV="phrases_eo_en_ja_zh_ko_ru_fulfilled_251130.csv"
OUT="grammar_errors.txt"
> "$OUT"

echo "=== Preposition + Accusative (Usually wrong, al/de/el etc don't take accusative) ===" >> "$OUT"
grep -P -n -i '\b(al|de|el|kun|per|pro|pri|sen|krom)\s+(la\s+)?(?!min|vin|lin|ŝin|ĝin|nin|ilin|sin|kiun|tiun|iun)[a-zĉĝĥĵŝŭ]+(on|an|ojn|ajn)\b' "$CSV" >> "$OUT"

echo "=== Adjective -a followed by Noun -oj, -on, -ojn (Mismatch) ===" >> "$OUT"
grep -P -n -i '\b(?!(la|da|kaj|aŭ|via|mia|lia|ŝia|ĝia|nia|ilia|sia|ĉia|tia|kia|nenia|ia)\b)[a-zĉĝĥĵŝŭ]+a\s+[a-zĉĝĥĵŝŭ]+o(j|n|jn)\b' "$CSV" >> "$OUT"

echo "=== Adjective -aj followed by Noun -o, -on, -ojn (Mismatch) ===" >> "$OUT"
grep -P -n -i '\b[a-zĉĝĥĵŝŭ]+aj\s+[a-zĉĝĥĵŝŭ]+o(n|jn)\b' "$CSV" >> "$OUT"

echo "=== Adjective -an followed by Noun -o, -oj, -ojn (Mismatch) ===" >> "$OUT"
grep -P -n -i '\b[a-zĉĝĥĵŝŭ]+an\s+[a-zĉĝĥĵŝŭ]+o(j|jn)\b' "$CSV" >> "$OUT"

echo "=== Adjective -ajn followed by Noun -o, -oj, -on (Mismatch) ===" >> "$OUT"
grep -P -n -i '\b[a-zĉĝĥĵŝŭ]+ajn\s+[a-zĉĝĥĵŝŭ]+o(j|n)\b' "$CSV" >> "$OUT"
