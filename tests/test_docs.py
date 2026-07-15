from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote

LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")


class DocumentationTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self) -> None:
        root = Path(__file__).resolve().parents[1]
        failures: list[str] = []
        for document in sorted(root.rglob("*.md")):
            if any(part in {".git", ".venv", "runtime", "__pycache__"} for part in document.parts):
                continue
            text = document.read_text(encoding="utf-8", errors="replace")
            for raw_target in LINK_RE.findall(text):
                target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
                if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = unquote(target.split("#", 1)[0])
                if not target:
                    continue
                resolved = (document.parent / target).resolve()
                try:
                    resolved.relative_to(root.resolve())
                except ValueError:
                    failures.append(f"{document.relative_to(root)} escapes repository: {raw_target}")
                    continue
                if not resolved.exists():
                    failures.append(f"{document.relative_to(root)} -> {raw_target}")
        self.assertFalse(failures, "Broken local Markdown links:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
