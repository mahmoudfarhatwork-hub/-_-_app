"""Shared helpers: load content, validate it, and normalize Arabic text for search."""

from __future__ import annotations

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent

# content sub-folder -> schema file name
COLLECTIONS = {
    "hadith": "hadith.schema.json",
    "adhkar": "dhikr.schema.json",
}

_ARABIC_LETTER = re.compile(r"[؀-ۿ]")
# tashkeel, superscript alef, Quranic annotation marks, tatweel
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_ALEF_VARIANTS = re.compile(r"[أإآٱ]")


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for search.

    Removes diacritics and tatweel, unifies alef forms, alef maqsura -> ya,
    ta marbuta -> ha, and collapses whitespace. The app should apply the same
    algorithm to the user's query so both sides match.
    """
    text = _DIACRITICS.sub("", text)
    text = _ALEF_VARIANTS.sub("ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"\s+", " ", text).strip()


def load_schema(root: Path, kind: str) -> dict:
    path = root / "content" / "schema" / COLLECTIONS[kind]
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _format_error(err) -> str:
    where = "/".join(str(p) for p in err.absolute_path) or "(item)"
    return f"{where}: {err.message}"


def validate(root: Path = ROOT):
    """Validate all content under `root`.

    Returns (items, errors) where items maps kind -> list of (file, item)
    for items that parsed as JSON objects, and errors is a list of strings.
    """
    items: dict[str, list[tuple[Path, dict]]] = {k: [] for k in COLLECTIONS}
    errors: list[str] = []
    seen_ids: dict[str, str] = {}

    for kind in COLLECTIONS:
        schema = load_schema(root, kind)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)

        folder = root / "content" / kind
        for path in sorted(folder.glob("*.json")):
            rel = path.relative_to(root).as_posix()
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"{rel}: invalid JSON ({exc})")
                continue
            if not isinstance(data, list):
                errors.append(f"{rel}: top level must be a JSON array of items")
                continue

            for index, item in enumerate(data):
                label = f"{rel}[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{label}: item must be an object")
                    continue
                item_id = item.get("id", "?")
                label = f"{label} ({item_id})"

                for err in sorted(validator.iter_errors(item), key=lambda e: list(e.absolute_path)):
                    errors.append(f"{label}: {_format_error(err)}")

                text = item.get("text_ar")
                if isinstance(text, str) and text.strip() and not _ARABIC_LETTER.search(text):
                    errors.append(f"{label}: text_ar has no Arabic letters")

                if isinstance(item_id, str) and item_id != "?":
                    if item_id in seen_ids:
                        errors.append(f"{label}: duplicate id, first seen in {seen_ids[item_id]}")
                    else:
                        seen_ids[item_id] = rel

                items[kind].append((path, item))

    return items, errors
