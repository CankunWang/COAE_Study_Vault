"""Audit Markdown code blocks for syntax and reusable-template hygiene."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^\s*(```|~~~)(\S*)\s*$")
NON_LOOPBACK_TARGET = re.compile(
    r"https?://(?!127\.0\.0\.1|localhost)(?:\d{1,3}\.){3}\d{1,3}:\d+"
)
REUSABLE_NOTES = {
    Path("技巧提示/COAE一阶规避攻击考试代码模板.md"),
    Path("_工具/EAD考试可复用代码库.md"),
}


@dataclass
class CodeBlock:
    language: str
    code: str
    opening_line: int


def extract_blocks(text: str) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []
    inside = False
    marker = ""
    language = ""
    opening_line = 0
    buffer: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = FENCE.match(line)
        if not inside and match:
            inside = True
            marker = match.group(1)
            language = match.group(2).lower()
            opening_line = line_number
            buffer = []
            continue
        if inside and re.match(rf"^\s*{re.escape(marker)}\s*$", line):
            blocks.append(
                CodeBlock(language, "\n".join(buffer), opening_line)
            )
            inside = False
            marker = ""
            language = ""
            buffer = []
            continue
        if inside:
            buffer.append(line)
    return blocks


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    errors: list[str] = []
    python_count = 0
    block_count = 0

    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        blocks = extract_blocks(text)
        block_count += len(blocks)

        for block_index, block in enumerate(blocks, start=1):
            if block.language != "python":
                continue
            python_count += 1
            try:
                ast.parse(block.code)
            except SyntaxError as error:
                local_line = error.lineno or 1
                actual_line = block.opening_line + local_line
                errors.append(
                    f"Python 代码块语法不完整：{relative}:{actual_line} "
                    f"({error.msg})"
                )

        if NON_LOOPBACK_TARGET.search(text):
            errors.append(f"保存了临时公网靶机地址：{relative}")

        if relative in REUSABLE_NOTES:
            for pattern, description in (
                (r"\bdef\s+solve_", "包含单题 solve_* 函数"),
                (r"HTB\{", "包含固定 Flag"),
                (r"STMIP|STMPO", "包含旧式靶机占位符"),
            ):
                if re.search(pattern, text):
                    errors.append(f"复用代码库{description}：{relative}")

    print(f"代码围栏：{block_count}")
    print(f"Python 代码块：{python_count}")
    print(f"错误：{len(errors)}")
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("代码块检查通过。")


if __name__ == "__main__":
    main()
