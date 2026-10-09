"""Conservative presentation projection for exact written-step verification."""

from dataclasses import dataclass
import re

from .answers import parse_answer, split_parts, strip_answer_label
from .parser import normalize_latex, ParseError


@dataclass(frozen=True)
class Layout:
    fragments: tuple[str, ...]
    unsupported: tuple[str, ...]


def written_layout(source: str) -> Layout:
    text = normalize_latex(strip_answer_label(source))
    unknown = []
    # Remove a *whole* presentation comment so its mathematical arguments do
    # not turn into new expressions (e.g. "subtracting x from both sides").
    text = re.sub(
        r"\(\s*\\text\{subtracting\s*\}\s*[^(){}]+\\text\{\s*from both sides\}\s*\)",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\\tag\{[^{}]*\}", "", text)
    text = re.sub(r"\\(?:cdots|ldots)\s*\(\d+\)", "", text)
    array = re.fullmatch(r"\\begin\{array\}\{[rlc]\}(.*?)\\end\{array\}", text, re.S)
    if array and r"\hline" in array[1]:
        above, below = array[1].split(r"\hline", 1)
        rows = [r.strip() for r in above.split(r"\\") if r.strip()]
        text = (
            "+".join("(" + row + ")" for row in rows)
            + "="
            + below.replace(r"\\", "").strip()
        )
    text = re.sub(r"\\(?:begin|end)\{(?:enumerate|itemize)\}", "", text)
    text = re.sub(r"\\item(?:\[[^]]*\])?", ";", text)
    text = text.replace(r"\(", "").replace(r"\)", "").replace("$", "")

    def annotation(match):
        content = match[1].strip().lower()
        if content in {"and", "i.e.", "i.e.,"}:
            return ";"
        if content in {"l.h.s.", "r.h.s.", "lhs", "rhs"}:
            return r"\label"
        if content in {
            "note that",
            "also,",
            "here,",
            "we have",
            "put",
            "then",
            "since",
            "for",
        }:
            return ""
        if content.startswith(
            ("subtracting ", "using commutativity", "(using commutativity")
        ):
            return ""
        unknown.append("Unsupported prose/condition: " + match[1].strip())
        return ";"

    text = re.sub(r"\\text\{([^{}]*)\}", annotation, text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\\(?:Rightarrow|implies|Leftrightarrow)(?![A-Za-z])", ";", text)
    text = text.replace(r"\{", "{").replace(r"\}", "}")
    # An integer declaration is part of the root family, not a separate
    # neighbouring statement. Only a fully parsed answer can use this path.
    if r"\mathbb{Z}" in text and parse_answer(text).status == "OK":
        return Layout((text,), tuple(unknown))
    fragments = []
    for fragment in split_parts(text):
        fragment = fragment.strip().rstrip(".,")
        if fragment.startswith(r"\label"):
            fragment = fragment[len(r"\label") :].lstrip().lstrip("=").strip()
        fragment = re.sub(r"=\s*\\label\s*$", "", fragment).strip()
        if not fragment:
            continue
        if r"\label" in fragment:
            raise ParseError("Presentation label inside an expression")
        fragments.append(fragment)
    return Layout(tuple(fragments), tuple(unknown))
