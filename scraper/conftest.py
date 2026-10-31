"""Dodaje scraper/ do sys.path, żeby testy działały niezależnie od katalogu uruchomienia."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
