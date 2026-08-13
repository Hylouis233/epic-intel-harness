"""Fast pre-publication scan for secret shapes and internal infrastructure markers."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SKIP_PARTS = {".git", ".venv", ".epic-intel", "artifacts", "dist", "build", "__pycache__"}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".svg",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
RULES = {
    "generic-secret": re.compile(
        r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?"
        r"[A-Za-z0-9_./+-]{16,}"
    ),
    "github-token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "openai-token": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "private-ip": re.compile(
        r"(?<!\d)(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?!\d)"
    ),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def scan(root: Path) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or set(path.parts).intersection(SKIP_PARTS):
            continue
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in RULES.items():
                if pattern.search(line):
                    findings.append((str(path.relative_to(root)), line_number, name))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    findings = scan(args.root.resolve())
    if findings:
        for path, line, rule in findings:
            print(f"{path}:{line}: {rule}")
        print(f"FAIL: {len(findings)} potential secret or internal-network markers")
        return 1
    print("PASS: no configured secret or internal-network markers found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
