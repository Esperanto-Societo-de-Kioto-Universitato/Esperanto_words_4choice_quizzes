import pandas as pd
import vocab_grouping as vg
from pathlib import Path
import random

CSV_DEFAULT = Path("2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv")


def verify_coverage():
    csv_path = CSV_DEFAULT
    df = pd.read_csv(csv_path)
    total_csv_words = len(df)
    print(f"Total words in CSV: {total_csv_words}")

    # Test with a few seeds to ensure consistency in total count
    for seed in [1, 42, 12345]:
        groups = vg.build_groups(csv_path, seed=seed)
        total_group_words = sum(g.size for g in groups)
        
        print(f"Seed {seed}: Total words in groups: {total_group_words}")
        
        # Check for duplicates or missing words
        all_ids = []
        for g in groups:
            for e in g.entries:
                all_ids.append(e.source_index)
        
        unique_ids = set(all_ids)
        if len(all_ids) != total_group_words:
            print(f"  WARNING: Total items {total_group_words} != len(all_ids) {len(all_ids)}")
        
        if len(unique_ids) != total_csv_words:
            print(f"  WARNING: Unique IDs {len(unique_ids)} != CSV rows {total_csv_words}")
            missing = set(range(total_csv_words)) - unique_ids
            print(f"  Missing indices: {list(missing)[:10]}...")
        else:
            print(f"  OK: All CSV rows are present exactly once.")

def verify_randomness():
    csv_path = CSV_DEFAULT
    
    # 1. Check if split_by_level is deterministic (same groups/levels for different seeds?)
    # Note: build_groups uses the seed for split_into_groups, so the *groups* will change.
    # But the *set of words* in "beginner", "intermediate", "advanced" should be identical BEFORE grouping.
    # However, vocab_grouping.py doesn't expose the intermediate buckets easily without modifying code.
    # We can check if the *POS* and *Level* assignment is consistent.
    
    groups1 = vg.build_groups(csv_path, seed=1)
    groups2 = vg.build_groups(csv_path, seed=2)
    
    # Check if a specific word is always in the same POS/Level category
    # We can map source_index -> (pos, stages)
    
    def map_word_info(groups):
        info = {}
        for g in groups:
            for e in g.entries:
                # stages is a list like ['beginner_1'], we care about the 'beginner' part mostly, 
                # but the user asked if "grouping within same POS/Level" is the only random part.
                # So 'beginner_1' might change to 'beginner_2' if the shuffle happens before sub-chunking?
                # Let's look at the code: 
                # split_by_level -> build_sublevels -> merge_small_sublevels -> THEN split_into_groups (shuffle happens here)
                # Wait, split_into_groups takes 'labels' and 'words'. 
                # The 'words' passed to split_into_groups are from 'merged' sublevels.
                # 'merged' comes from 'build_sublevels' which uses 'even_chunks' on 'buckets'.
                # 'buckets' comes from 'split_by_level' which sorts by unified_level.
                # So the assignment to 'beginner_1', 'beginner_2' etc. should be DETERMINISTIC.
                # The SHUFFLE happens inside `split_into_groups`.
                # So a word should ALWAYS belong to the same "Stage Label" (e.g. beginner_1).
                # AND the same POS.
                info[e.source_index] = (g.pos, tuple(g.stages))
        return info

    info1 = map_word_info(groups1)
    info2 = map_word_info(groups2)
    
    diffs = 0
    for idx in info1:
        if info1[idx] != info2[idx]:
            diffs += 1
            # print(f"Diff: Idx {idx} {info1[idx]} vs {info2[idx]}")
            
    if diffs == 0:
        print("OK: POS and Level/Sublevel assignments are DETERMINISTIC (unaffected by seed).")
    else:
        print(f"WARNING: {diffs} words changed their POS or Level/Sublevel assignment between seeds.")

    # 2. Check if grouping WITHIN the same stage is random
    # We expect that for the same stage (e.g. beginner_1), the words are distributed into g1, g2... differently.
    # Or if there is only 1 group, the order inside might be different?
    # Group object has 'entries'.
    
    # Let's pick a stage that likely has multiple groups.
    # We need to find a stage with > 30 words.
    
    # 3. Check Question Order Randomness
    # app.py uses random.Random() (no seed) for build_questions_for_group.
    # We can simulate this.
    g1 = groups1[0]
    rng_q1 = random.Random(123)
    q1 = vg.build_questions_for_group(g1, rng=rng_q1)
    
    rng_q2 = random.Random(456)
    q2 = vg.build_questions_for_group(g1, rng=rng_q2)
    
    # Check if prompts are in different order
    prompts1 = [q['prompt'] for q in q1]
    prompts2 = [q['prompt'] for q in q2]
    
    if prompts1 != prompts2:
        print("OK: Question order is randomized independently of the group.")
    else:
        print("WARNING: Question order seems identical (unlikely unless group is tiny).")

    # Check if all words in group are used in questions
    if len(q1) == len(g1.entries):
        print("OK: All words in the group are used as questions exactly once.")
    else:
        print(f"WARNING: Group size {len(g1.entries)} but generated {len(q1)} questions.")

def verify_audio_existence():
    csv_path = CSV_DEFAULT
    audio_dir = Path("audio")
    df = pd.read_csv(csv_path)
    
    missing_count = 0
    total_words = len(df)
    
    print(f"Checking audio for {total_words} words...")
    
    for idx, row in df.iterrows():
        word = str(row["Esperanto"]).strip()
        if not word:
            continue
            
        key = vg._default_audio_key(word)
        # Try common extensions
        found = False
        for ext in [".wav", ".mp3", ".ogg"]:
            if (audio_dir / f"{key}{ext}").exists():
                found = True
                break
        
        if not found:
            missing_count += 1
            if missing_count <= 10:
                print(f"  Missing audio for: {word} (key: {key})")
    
    if missing_count == 0:
        print(f"OK: All {total_words} words have corresponding audio files.")
    else:
        print(f"WARNING: {missing_count} words are missing audio files.")

if __name__ == "__main__":
    print("--- Verifying Coverage ---")
    verify_coverage()
    print("\n--- Verifying Randomness ---")
    verify_randomness()
    print("\n--- Verifying Audio ---")
    verify_audio_existence()
