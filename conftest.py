"""Make mower_sdk importable from the checkout without installation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
