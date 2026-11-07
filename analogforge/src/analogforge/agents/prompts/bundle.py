"""Versioned prompt bundle with untrusted source text isolated in user data."""

from pathlib import Path

from analogforge.ports.hashing import canonical_sha256
from analogforge.tools.allowlist import allowed_tools

ROOT = Path(__file__).parent


def prompt_bundle(role: str) -> tuple[str, str]:
    if role not in {p.stem for p in ROOT.glob("*.md")}:
        raise ValueError("Unknown role")
    prompt = (ROOT / "COMMON_POLICY.md").read_text() + "\n" + (ROOT / f"{role}.md").read_text()
    return prompt, canonical_sha256({"version": "1.0.0", "prompt": prompt, "tools": sorted(allowed_tools(role))})
