import copy
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.build_db import build
from tools.common import ROOT, normalize_arabic, validate


def make_repo(hadith=None, adhkar=None) -> Path:
    """Copy the real schemas into a temp repo and write the given content."""
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "content" / "schema", tmp / "content" / "schema")
    (tmp / "content" / "hadith").mkdir(parents=True)
    (tmp / "content" / "adhkar").mkdir(parents=True)
    (tmp / "content" / "hadith" / "t.json").write_text(
        json.dumps(hadith or [], ensure_ascii=False), encoding="utf-8"
    )
    (tmp / "content" / "adhkar" / "t.json").write_text(
        json.dumps(adhkar or [], ensure_ascii=False), encoding="utf-8"
    )
    return tmp


# Synthetic fixtures: they test the rules only and make no religious claim.
GOOD_HADITH = {
    "id": "test-001",
    "text_ar": "نص تجريبي",
    "narrator": "راوٍ تجريبي",
    "graded_by": ["مخرّج تجريبي"],
    "sources": [{"book": "كتاب تجريبي", "number": "1"}],
    "grade": "sahih",
    "category": "authentic",
    "review_status": "draft",
}
GOOD_DHIKR = {
    "id": "test-dhikr-001",
    "text_ar": "ذكر تجريبي",
    "category": "morning",
    "repeat": 3,
    "sources": [{"type": "hadith", "ref": "مصدر تجريبي 1", "grade": "sahih"}],
    "review_status": "draft",
}


class RealContentTest(unittest.TestCase):
    def test_repo_content_is_valid(self):
        _, errors = validate(ROOT)
        self.assertEqual(errors, [])


class HadithRulesTest(unittest.TestCase):
    def errors_for(self, **overrides):
        item = copy.deepcopy(GOOD_HADITH)
        for key, value in overrides.items():
            if value is None:
                item.pop(key, None)
            else:
                item[key] = value
        _, errors = validate(make_repo(hadith=[item]))
        return errors

    def test_good_item_passes(self):
        self.assertEqual(self.errors_for(), [])

    def test_missing_narrator_rejected(self):
        self.assertTrue(self.errors_for(narrator=None))

    def test_missing_sources_rejected(self):
        self.assertTrue(self.errors_for(sources=[]))

    def test_unknown_field_rejected(self):
        self.assertTrue(self.errors_for(gradee="sahih"))

    def test_weak_must_be_in_warning_category(self):
        self.assertTrue(self.errors_for(grade="daif", category="authentic"))
        self.assertEqual(self.errors_for(grade="daif", category="warning"), [])

    def test_warning_category_only_accepts_weak_or_fabricated(self):
        self.assertTrue(self.errors_for(grade="sahih", category="warning"))

    def test_published_requires_reviewer(self):
        self.assertTrue(self.errors_for(review_status="published"))
        self.assertEqual(
            self.errors_for(review_status="published", reviewer="مراجع", reviewed_at="2026-10-07"),
            [],
        )

    def test_text_without_arabic_rejected(self):
        self.assertTrue(self.errors_for(text_ar="only latin text"))

    def test_duplicate_ids_rejected(self):
        _, errors = validate(make_repo(hadith=[GOOD_HADITH, GOOD_HADITH]))
        self.assertTrue(any("duplicate id" in e for e in errors))


class DhikrRulesTest(unittest.TestCase):
    def test_good_item_passes(self):
        _, errors = validate(make_repo(adhkar=[GOOD_DHIKR]))
        self.assertEqual(errors, [])

    def test_hadith_source_requires_grade(self):
        item = copy.deepcopy(GOOD_DHIKR)
        del item["sources"][0]["grade"]
        _, errors = validate(make_repo(adhkar=[item]))
        self.assertTrue(errors)

    def test_repeat_must_be_positive(self):
        item = copy.deepcopy(GOOD_DHIKR)
        item["repeat"] = 0
        _, errors = validate(make_repo(adhkar=[item]))
        self.assertTrue(errors)

    def test_id_unique_across_collections(self):
        item = copy.deepcopy(GOOD_DHIKR)
        item["id"] = GOOD_HADITH["id"]
        _, errors = validate(make_repo(hadith=[GOOD_HADITH], adhkar=[item]))
        self.assertTrue(any("duplicate id" in e for e in errors))


class NormalizeTest(unittest.TestCase):
    def test_removes_diacritics_and_unifies_letters(self):
        self.assertEqual(normalize_arabic("إِنَّمَا الْأَعْمَالُ"), "انما الاعمال")
        self.assertEqual(normalize_arabic("هِجْرَتُهُ"), "هجرته")

    def test_alef_maqsura_and_ta_marbuta(self):
        self.assertEqual(normalize_arabic("مَا نَوَى"), "ما نوي")
        self.assertEqual(normalize_arabic("الصلاة"), "الصلاه")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_arabic("  كلمة   كلمة "), "كلمه كلمه")


class BuildDbTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo(hadith=[GOOD_HADITH], adhkar=[GOOD_DHIKR])
        self.out = self.repo / "build" / "c.db"

    def test_default_build_excludes_drafts(self):
        counts = build(self.repo, self.out, include_draft=False)
        self.assertEqual(counts, {"hadith": 0, "dhikr": 0})

    def test_dev_build_includes_drafts_and_search_works(self):
        counts = build(self.repo, self.out, include_draft=True)
        self.assertEqual(counts, {"hadith": 1, "dhikr": 1})
        con = sqlite3.connect(self.out)
        try:
            query = normalize_arabic("تجريبي")
            rows = con.execute(
                "SELECT kind, id FROM search_fts WHERE search_fts MATCH ?", (query,)
            ).fetchall()
            self.assertEqual(set(rows), {("dhikr", "test-dhikr-001"), ("hadith", "test-001")})
            src = con.execute("SELECT book, number FROM hadith_source").fetchall()
            self.assertEqual(src, [("كتاب تجريبي", "1")])
        finally:
            con.close()

    def test_search_matches_word_inside_prefixed_word(self):
        item = copy.deepcopy(GOOD_HADITH)
        item["text_ar"] = "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ"
        repo = make_repo(hadith=[item])
        build(repo, repo / "build" / "c.db", include_draft=True)
        con = sqlite3.connect(repo / "build" / "c.db")
        try:
            query = '"%s"' % normalize_arabic("النيات")
            rows = con.execute("SELECT id FROM search_fts WHERE search_fts MATCH ?", (query,)).fetchall()
            self.assertEqual(rows, [("test-001",)])
        finally:
            con.close()

    def test_published_item_is_included_by_default(self):
        item = copy.deepcopy(GOOD_HADITH)
        item.update(review_status="published", reviewer="مراجع", reviewed_at="2026-10-07")
        repo = make_repo(hadith=[item])
        counts = build(repo, repo / "build" / "c.db", include_draft=False)
        self.assertEqual(counts["hadith"], 1)

    def test_build_refuses_invalid_content(self):
        bad = copy.deepcopy(GOOD_HADITH)
        del bad["narrator"]
        repo = make_repo(hadith=[bad])
        with self.assertRaises(ValueError):
            build(repo, repo / "build" / "c.db", include_draft=True)


if __name__ == "__main__":
    unittest.main()
