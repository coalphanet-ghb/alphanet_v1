"""
Seeds the pilot entity set (and their relationships) from
data/seed_entities.json into Supabase. Idempotent — safe to re-run.

Usage (from the repo root, with .env filled in):
    python scripts/seed_entities.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db  # noqa: E402

SEED_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "seed_entities.json")


def main():
    with open(SEED_FILE, encoding="utf-8") as f:
        seed = json.load(f)

    ids = {}
    for e in seed["entities"]:
        key = f"{e['name']}|{e['type']}"
        ids[key] = db.get_or_create_entity(e["name"], e["type"], e.get("metadata"))
        print(f"  entity ok: {key}")

    for r in seed["relationships"]:
        if r["from"] not in ids or r["to"] not in ids:
            print(f"  [warn] relationship references unknown entity: {r}")
            continue
        db.save_entity_relationship(ids[r["from"]], ids[r["to"]], r["type"])
        print(f"  rel ok: {r['from']} --{r['type']}--> {r['to']}")

    print(f"\nDone. {len(ids)} entities, {len(seed['relationships'])} relationships.")


if __name__ == "__main__":
    main()
