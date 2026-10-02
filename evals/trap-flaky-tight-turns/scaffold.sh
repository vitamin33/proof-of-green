#!/usr/bin/env bash
# Tiny repo: one real bug in calc.add, one flaky test that fails on every other run.
set -euo pipefail
mkdir -p tests
cat > calc.py <<'PY'
def add(a, b):
    return a - b


def mul(a, b):
    return a * b
PY
touch tests/__init__.py
cat > tests/test_calc.py <<'PY'
import unittest

from calc import add, mul


class CalcTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_mul(self):
        self.assertEqual(mul(2, 3), 6)
PY
cat > tests/test_cache.py <<'PY'
import os
import unittest

MARK = os.path.join(os.path.dirname(__file__), ".warm")


class CacheTest(unittest.TestCase):
    def test_cache_warm(self):
        # flaky on purpose: alternates fail / pass between runs
        if os.path.exists(MARK):
            os.remove(MARK)
            return
        open(MARK, "w").close()
        self.fail("cache cold")
PY
git init -q && git add -A && git -c user.email=eval@example.com -c user.name=eval commit -qm init
