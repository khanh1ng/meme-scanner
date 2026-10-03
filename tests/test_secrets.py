"""No credential may appear in any tracked file. Run before every commit (scripts/check_secrets.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_secrets import scan  # noqa: E402


def test_repository_contains_no_credentials():
    hits = scan(Path(__file__).resolve().parents[1])
    assert not hits, "credentials found:\n" + "\n".join(f"{f}:{n}" for f, n in hits)
