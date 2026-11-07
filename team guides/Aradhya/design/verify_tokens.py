#!/usr/bin/env python3
"""Verify design/tokens.json: WCAG 2.2 contrast rules + state-colour distinctness.

Usage: python3 verify_tokens.py [path/to/tokens.json] [--json out.json]
Exit 0 only if every rule passes in every theme. Pure stdlib.
"""
from __future__ import annotations
import itertools, json, math, sys
from pathlib import Path


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def luminance(h: str) -> float:
    r, g, b = _rgb(h)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _lab(h: str) -> tuple[float, float, float]:
    r, g, b = (_lin(v) for v in _rgb(h))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: str, b: str) -> float:
    return math.dist(_lab(a), _lab(b))


def _as_list(v):
    return v if isinstance(v, list) else [v]


def verify(doc: dict) -> list[dict]:
    results: list[dict] = []
    for theme, colors in doc["themes"].items():
        for rule in doc["contrast_rules"]:
            for fg in _as_list(rule["fg"]):
                bgs = [fg + "-bg"] if rule["bg"] == "own-bg" else _as_list(rule["bg"])
                for bg in bgs:
                    ratio = contrast(colors[fg], colors[bg])
                    ok = ratio >= rule["min"]
                    results.append({"theme": theme, "rule": rule["id"], "fg": fg, "bg": bg,
                                    "ratio": round(ratio, 2), "min": rule["min"], "ok": ok})
        names = [k for k in colors if k.startswith("state-") and not k.endswith("-bg")]
        for a, b in itertools.combinations(names, 2):
            d = delta_e(colors[a], colors[b])
            results.append({"theme": theme, "rule": "D1", "fg": a, "bg": b, "ratio": round(d, 1),
                            "min": doc["distinctness_rules"][0]["min_delta_e"],
                            "ok": d >= doc["distinctness_rules"][0]["min_delta_e"]})
    return results


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    path = Path(args[0]) if args else Path(__file__).with_name("tokens.json")
    doc = json.loads(path.read_text())
    res = verify(doc)
    bad = [r for r in res if not r["ok"]]
    if "--json" in argv:
        out = Path(argv[argv.index("--json") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"checked": len(res), "failed": len(bad), "failures": bad}, indent=2))
    for r in bad:
        print(f"FAIL [{r['theme']}] {r['rule']} {r['fg']} on {r['bg']}: {r['ratio']} < {r['min']}")
    print(f"{len(res) - len(bad)}/{len(res)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
