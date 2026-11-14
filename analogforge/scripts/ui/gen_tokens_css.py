#!/usr/bin/env python3
"""Generate styles/tokens.css from design/tokens.json (deterministic). UIX-12 compares the committed file with this output.

Usage: python3 gen_tokens_css.py [tokens.json] [--out path]   (prints to stdout without --out)
Dark is the default theme (:root and [data-theme="dark"]); light is [data-theme="light"] and @media print.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

STATIC = """  --font-sans: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 48px;
  --radius-0: 0; --radius-1: 2px; --radius-2: 4px; --radius-3: 6px;
  --text-xs: 12px; --text-sm: 13px; --text-md: 14px; --text-lg: 16px; --text-xl: 20px; --text-2xl: 24px;
  --lh-tight: 1.25; --lh-normal: 1.45;
  --row-h-compact: 28px; --row-h-default: 36px; --row-h-comfortable: 44px;
  --control-h: 32px; --control-h-touch: 44px;
  --focus-width: 2px; --focus-offset: 2px;
  --dur-fast: 100ms; --dur-base: 160ms; --ease: cubic-bezier(0.2, 0, 0, 1);
  --header-h: 48px; --left-w: 264px; --right-w: 352px; --ops-h: 220px;
"""


def block(selector: str, colors: dict[str, str]) -> str:
    body = "".join(f"  --{k}: {v};\n" for k, v in sorted(colors.items()))
    return f"{selector} {{\n{body}}}\n"


def render(doc: dict) -> str:
    dark, light = doc["themes"]["dark"], doc["themes"]["light"]
    out = ["/* GENERATED from design/tokens.json by scripts/ui/gen_tokens_css.py. Do not edit by hand. */\n"]
    out.append(':root {\n' + STATIC + '  color-scheme: dark;\n}\n')
    out.append(block(':root, [data-theme="dark"]', dark))
    out.append(block('[data-theme="light"]', light))
    out.append('@media print {\n' + block(':root', light).replace('\n', '\n  ').rstrip(' ') + '}\n')
    return "\n".join(out)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    src = Path(args[0]) if args and not (argv.index(args[0]) > 0 and argv[argv.index(args[0]) - 1] == "--out") else Path(__file__).with_name("tokens.json")
    doc = json.loads(src.read_text())
    css = render(doc)
    if "--out" in argv:
        Path(argv[argv.index("--out") + 1]).write_text(css)
    else:
        sys.stdout.write(css)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
