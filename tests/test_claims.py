import json
import os
import re

import pytest

from falsegreen import claims

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _load(name):
    with open(os.path.join(CORPUS, name), encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


POS = _load("claims_positive.jsonl")
NEG = _load("claims_negative.jsonl")


def test_corpus_size_and_languages():
    for rows in (POS, NEG):
        assert len(rows) >= 40
        langs = {r["lang"] for r in rows}
        assert langs == {"en", "uk"}


def test_precision_on_corpus():
    tp = fp = fn = 0
    for row in POS:
        got = {c["type"] for c in claims.extract(row["text"])}
        exp = set(row["types"])
        tp += len(got & exp)
        fp += len(got - exp)
        fn += len(exp - got)
    neg_hits = [row["text"] for row in NEG if claims.extract(row["text"])]
    fp += len(neg_hits)
    precision = tp / float(tp + fp)
    recall = tp / float(tp + fn)
    assert len(neg_hits) / float(len(NEG)) <= 0.05, neg_hits
    assert precision >= 0.95
    assert recall >= 0.80


@pytest.mark.parametrize("row", NEG, ids=lambda r: r["text"][:40])
def test_negative_examples_have_no_claim(row):
    assert claims.extract(row["text"]) == []


@pytest.mark.parametrize("pattern", claims.PATTERNS, ids=lambda p: p.example)
def test_every_pattern_matches_its_example(pattern):
    assert re.search(pattern.rx, pattern.example, re.I)
    assert pattern.type in {c["type"] for c in claims.extract(pattern.example)}


def test_scope_all_vs_partial():
    assert claims.extract("All 40 tests pass.")[0]["scope"] == "all"
    assert claims.extract("The new tests pass.")[0]["scope"] == "partial"
    assert claims.extract("test_login passes now.")[0]["scope"] == "partial"
    assert claims.extract("42 passed in 0.31s.")[0]["scope"] == "all"


def test_one_claim_per_type_and_stable_order():
    out = claims.extract("Done. Fixed it. All tests pass. Also fixed the typo.")
    assert [c["type"] for c in out] == ["tests_pass", "done", "fixed"]


def test_code_blocks_and_quotes_are_ignored():
    assert claims.extract("Output:\n```\n12 passed in 0.4s\nDone.\n```") == []
    assert claims.extract('The issue title was "Fixed the login bug".') == []
