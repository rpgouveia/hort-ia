"""Build data/knowledge/companions.csv from the Kaggle "Companion Plants" dataset.

Source: https://www.kaggle.com/datasets/aramacus/companion-plants (derived from the
Wikipedia "List of companion plants", CC BY-SA). The raw CSV is not versioned:
download it to data/raw/companion_plants.csv before running this script.

All rows produced here get evidence="traditional": the dataset gives no mechanism
and most claims are gardening tradition, not field trials.

Usage: uv run python scripts/build_companions_v1.py [path/to/companion_plants.csv]
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw" / "companion_plants.csv"
OUT = ROOT / "data" / "knowledge" / "companions.csv"
SOURCE_ID = "kaggle_companion_plants"

# Dataset node -> crop ids. Decisions:
# - "peppers"/"capsicum" -> pimentao; "chili peppers" excluded (other crop).
# - "squash" -> abobrinha (Cucurbita pepo is a squash); "pumpkins"/"gourds" excluded.
# - "chives"/"green onions" -> cebolinha; onion, garlic, leek, shallots excluded (other crops).
# - "kale cabbage" is a parsing artifact of "kale, cabbage" -> couve and repolho.
DIRECT = {
    "tomatoes": ["tomate"], "potato": ["batata"], "potatoes": ["batata"],
    "capsicum": ["pimentao"], "peppers": ["pimentao"], "strawberries": ["morango"],
    "lettuce": ["alface"], "kale cabbage": ["couve", "repolho"],
    "cabbage": ["repolho"], "cabbages": ["repolho"], "carrots": ["cenoura"],
    "beetroot": ["beterraba"], "beets": ["beterraba"], "radish": ["rabanete"],
    "radishes": ["rabanete"], "chives": ["cebolinha"], "green onions": ["cebolinha"],
    "parsley": ["salsa"], "basil": ["manjericao"], "zucchini": ["abobrinha"],
    "squash": ["abobrinha"],
}

# Group nodes expanded to the crops they contain. Decisions:
# - "brassicas" = cole crops (Brassica oleracea): couve, repolho. Rúcula (Eruca) and
#   rabanete (Raphanus) are Brassicaceae but not "brassicas" in gardening usage.
# - "alliums" -> cebolinha only, since it is the only allium among our crops.
GROUPS = {
    "alliums": ["cebolinha"],
    "brassicas": ["couve", "repolho"],
    "nightshades": ["tomate", "batata", "pimentao"],
    "cucurbits": ["abobrinha"],
}


def resolve(node: str) -> tuple[list[str], str | None]:
    if node in DIRECT:
        return DIRECT[node], None
    if node in GROUPS:
        return GROUPS[node], node
    return [], None


def main() -> None:
    # (a, b) -> relation -> set of origins ("direct" or "grupo '<name>'")
    directed: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    with RAW.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            src, link, dst = row["Source Node"].strip(), row["Link"].strip(), row["Destination Node"].strip()
            src_crops, src_group = resolve(src)
            dst_crops, dst_group = resolve(dst)
            groups = sorted(g for g in (src_group, dst_group) if g)
            origin = " + ".join(f"grupo '{g}'" for g in groups) or "direct"
            for a in src_crops:
                for b in dst_crops:
                    if a == b:
                        continue
                    if link == "helps":
                        directed[(a, b)]["helps"].add(origin)
                    elif link == "helped_by":  # b helps a
                        directed[(b, a)]["helps"].add(origin)
                    elif link == "avoid":  # do not plant together: mutual by nature
                        directed[tuple(sorted((a, b)))]["harms"].add(origin)

    rows, conflicts = [], []
    done: set[tuple[str, str]] = set()
    for (a, b), relations in sorted(directed.items()):
        pair = tuple(sorted((a, b)))
        if pair in done:
            continue
        done.add(pair)
        reverse = directed.get((b, a), {})
        harms = relations.get("harms", set()) | reverse.get("harms", set())
        helps_ab, helps_ba = relations.get("helps", set()), reverse.get("helps", set())
        if harms and (helps_ab or helps_ba):
            # Conflict policy: a statement about the crop itself beats one inherited
            # from a group; if both (or neither) sides are direct, leave the pair out.
            harms_direct = "direct" in harms
            helps_direct = "direct" in (helps_ab | helps_ba)
            if harms_direct == helps_direct:
                conflicts.append((pair, harms, helps_ab | helps_ba))
                continue
            note = "Conflito no dataset: relação direta prevaleceu sobre a herdada de grupo."
            if harms_direct:
                rows.append(_row(*pair, "harms", True, {"direct"}, note))
                continue
            harms = set()
            helps_ab = {o for o in helps_ab if o == "direct"}
            helps_ba = {o for o in helps_ba if o == "direct"}
            extra = note
        else:
            extra = ""
        if harms:
            rows.append(_row(*pair, "harms", True, harms, extra))
        elif helps_ab and helps_ba:
            rows.append(_row(*pair, "helps", True, helps_ab | helps_ba, extra))
        elif helps_ab:
            rows.append(_row(a, b, "helps", False, helps_ab, extra))
        else:
            rows.append(_row(b, a, "helps", False, helps_ba, extra))

    fields = ["crop_a", "crop_b", "relation", "mutual", "mechanism", "evidence",
              "source_id", "pages", "validation_status", "notes"]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} relations written to {OUT}")
    if conflicts:
        print(f"{len(conflicts)} conflicting pairs left out (resolve manually):")
        for pair, harms, helps in conflicts:
            print(f"  {pair}: avoid via {sorted(harms)} x helps via {sorted(helps)}")


def _row(a: str, b: str, relation: str, mutual: bool, origins: set[str], extra: str = "") -> dict:
    groups = sorted(o for o in origins if o != "direct")
    note = "" if "direct" in origins else "Expandido de " + "; ".join(groups) + " no dataset."
    note = " ".join(n for n in (note, extra) if n)
    return {"crop_a": a, "crop_b": b, "relation": relation, "mutual": str(mutual).lower(),
            "mechanism": "unknown", "evidence": "traditional", "source_id": SOURCE_ID,
            "pages": "", "validation_status": "draft", "notes": note}


if __name__ == "__main__":
    main()
