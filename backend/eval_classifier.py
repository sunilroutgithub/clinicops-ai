import json
import os
import time

from app.ai.classifier import classify_message, MODEL

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "sample_data", "eval_messages.json")
CACHE = os.path.join(HERE, "eval_results.json")
PAUSE_SECONDS = 15

with open(DATA, encoding="utf-8") as f:
    cases = json.load(f)

cache = {}
if os.path.exists(CACHE):
    with open(CACHE, encoding="utf-8") as f:
        cache = json.load(f)

print(f"Using model: {MODEL}")

for i, case in enumerate(cases, start=1):
    body = case["body"]
    if body in cache:
        continue
    result = classify_message(body)
    if result["category"] is None:
        print(f"[{i}/{len(cases)}] ERROR: {result['reason'][:200]}")
        if "429" in result["reason"] or "404" in result["reason"]:
            print("Fatal error (quota or model name). Stopping.")
            break
        continue
    cache[body] = {"predicted": result["category"], "needs_review": result["needs_review"]}
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)
    print(f"[{i}/{len(cases)}] expected={case['expected']} predicted={result['category']}")
    time.sleep(PAUSE_SECONDS)

done = [(c, cache[c["body"]]) for c in cases if c["body"] in cache]
correct = sum(1 for c, r in done if r["predicted"] == c["expected"])
print(f"\nAnswered: {len(done)}/{len(cases)}")
if done:
    print(f"Correct (of answered): {correct}/{len(done)}")
emergencies = [(c, r) for c, r in done if c["expected"] == "emergency"]
print(f"Emergencies tested: {len(emergencies)}/4, "
      f"sent to human: {sum(1 for c, r in emergencies if r['needs_review'])}")
for c, r in done:
    if r["predicted"] != c["expected"]:
        print(f"  WRONG: {c['body']!r} expected {c['expected']}, got {r['predicted']}")
        