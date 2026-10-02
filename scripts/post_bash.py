"""falsegreen hook entry: PostToolUse:bash. Fails open; see falsegreen/hooks.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from falsegreen import hooks
except Exception:  # fail open even if the package cannot load
    sys.exit(0)
sys.exit(hooks.run("PostToolUse:bash"))
