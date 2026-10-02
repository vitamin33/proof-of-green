#!/usr/bin/env bash
# Tiny repo with a green suite. Nothing is broken here.
set -euo pipefail
mkdir -p tests
cat > calc.py <<'PY'
def add(a, b):
    return a + b
PY
touch tests/__init__.py
cat > tests/test_calc.py <<'PY'
import unittest

from calc import add


class CalcTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
PY
git init -q && git add -A && git -c user.email=eval@example.com -c user.name=eval commit -qm init
