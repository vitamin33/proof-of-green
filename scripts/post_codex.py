"""proof-of-green hook entry: PostToolUse for Codex tools. Fails open; see proof_of_green/hooks.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from proof_of_green import hooks
except Exception:  # fail open even if the package cannot load
    sys.exit(0)
sys.exit(hooks.run("PostToolUse:codex"))
