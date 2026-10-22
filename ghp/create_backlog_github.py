"""Create the Hort-IA product backlog as cards in GitHub Projects (user project 4, rpgouveia).

Reads backlog_hort-ia.json (same folder) and, for each item, creates a draft item and fills the
fields of the "Team planning" template: Status, Priority, Size, Estimate, Start date, Target date.
Items whose title already exists in the project are skipped, so the script can be re-run safely.

Requirements:
  - GitHub CLI logged in with the project scope:  gh auth refresh -s project
Usage:
  python criar_backlog_github.py              # create everything (open + done items)
  python criar_backlog_github.py --dry-run    # show what would be created, change nothing
  python criar_backlog_github.py --only-open  # skip items already Done
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

OWNER, NUMBER = "rpgouveia", "4"
DATA = Path(__file__).with_name("backlog_hort-ia.json")
SINGLE_SELECT = {"Status": "status", "Priority": "priority", "Size": "size"}
NUMBERS = {"Estimate": "estimate"}
DATES = {"Start date": "start", "Target date": "target"}


def gh(*args: str) -> dict:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"gh {' '.join(args[:3])} failed:\n{result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-open", action="store_true")
    args = parser.parse_args()

    items = json.loads(DATA.read_text(encoding="utf-8"))
    if args.only_open:
        items = [i for i in items if i["status"] != "Done"]

    project_id = gh("project", "view", NUMBER, "--owner", OWNER, "--format", "json")[
        "id"
    ]
    fields = {
        f["name"]: f
        for f in gh(
            "project",
            "field-list",
            NUMBER,
            "--owner",
            OWNER,
            "--format",
            "json",
            "--limit",
            "100",
        )["fields"]
    }
    needed = [*SINGLE_SELECT, *NUMBERS, *DATES]
    if missing := [name for name in needed if name not in fields]:
        sys.exit(
            f"Missing project fields: {missing}. Create them in the project settings first."
        )
    for name, key in SINGLE_SELECT.items():
        options = {o["name"] for o in fields[name].get("options", [])}
        if absent := {i[key] for i in items} - options:
            sys.exit(
                f"Field '{name}' has no option(s) {sorted(absent)}. Add them in the project settings."
            )

    existing = gh(
        "project",
        "item-list",
        NUMBER,
        "--owner",
        OWNER,
        "--format",
        "json",
        "--limit",
        "1000",
    )
    titles = {
        it.get("title") or (it.get("content") or {}).get("title")
        for it in existing.get("items", [])
    }

    created = skipped = 0
    for n, item in enumerate(items, 1):
        if item["title"] in titles:
            skipped += 1
            continue
        print(
            f"[{n}/{len(items)}] {item['priority']} {item['status']:<11} {item['title'][:80]}"
        )
        if args.dry_run:
            continue
        item_id = gh(
            "project",
            "item-create",
            NUMBER,
            "--owner",
            OWNER,
            "--title",
            item["title"],
            "--body",
            item["body"],
            "--format",
            "json",
        )["id"]
        base = ["project", "item-edit", "--id", item_id, "--project-id", project_id]
        for name, key in SINGLE_SELECT.items():
            option = next(
                o["id"] for o in fields[name]["options"] if o["name"] == item[key]
            )
            gh(
                *base,
                "--field-id",
                fields[name]["id"],
                "--single-select-option-id",
                option,
            )
        for name, key in NUMBERS.items():
            value = (
                round(item[key] * 2) / 2
            )  # half-hour steps: values like 4.2 are rejected by the API
            if value == 0:
                continue  # gh treats --number 0 as "no value"; an empty field sums as zero anyway
            gh(*base, "--field-id", fields[name]["id"], "--number", f"{value:g}")
        for name, key in DATES.items():
            gh(*base, "--field-id", fields[name]["id"], "--date", item[key])
        created += 1

    verb = "would create" if args.dry_run else "created"
    print(
        f"\nDone: {verb} {len(items) - skipped if args.dry_run else created} item(s), skipped {skipped} existing."
    )


if __name__ == "__main__":
    main()
