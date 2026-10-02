"""Print the falsegreen report. Usage: report.py [--all] [--data DIR]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from falsegreen import report  # noqa: E402

sys.exit(report.main(sys.argv[1:]))
