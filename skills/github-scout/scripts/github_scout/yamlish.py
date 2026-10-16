"""The small YAML subset used in registry frontmatter.

Registry files must stay readable by any YAML parser and writable by agents
without a dependency, so the tool reads and writes only this subset:

    key: scalar              # plain, "double-quoted" (JSON escapes) or 'single'
    key: [a, "b c", 3]       # inline list of scalars
    key:                     # block list of scalars ...
      - a
    key:                     # ... or of flat mappings whose values are
      - name: x              #     scalars or inline lists
        tags: [a, b]

Anything else (nested mappings, block scalars, anchors, flow mappings) is a
FormatError with the line number, so a hand edit that drifts outside the
subset is reported instead of silently misread.
"""

from __future__ import annotations

import json
import re

__all__ = ["FormatError", "parse", "dump", "split_frontmatter", "join_frontmatter"]


class FormatError(ValueError):
    pass


_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$")
_INT = re.compile(r"^-?(0|[1-9][0-9]*)$")
_PLAIN_SAFE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./@+-]*$")
_RESERVED = {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}


def _strip_comment(text: str) -> str:
    """Remove a trailing ' #comment' from a plain scalar (quotes handled by callers)."""
    m = re.search(r"\s#", text)
    return text[: m.start()].rstrip() if m else text.rstrip()


def _scalar(raw: str, line: int):
    s = raw.strip()
    if s == "":
        return None
    if s[0] == '"':
        end = _closing_double(s, line)
        rest = s[end + 1 :].strip()
        if rest and not rest.startswith("#"):
            raise FormatError(f"line {line}: text after closing quote: {rest!r}")
        try:
            return json.loads(s[: end + 1])
        except json.JSONDecodeError as exc:
            raise FormatError(f"line {line}: bad double-quoted string ({exc.msg})") from None
    if s[0] == "'":
        i, out = 1, []
        while i < len(s):
            if s[i] == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                rest = s[i + 1 :].strip()
                if rest and not rest.startswith("#"):
                    raise FormatError(f"line {line}: text after closing quote: {rest!r}")
                return "".join(out)
            out.append(s[i])
            i += 1
        raise FormatError(f"line {line}: unterminated single-quoted string")
    if s[0] in "{&*!|>":
        raise FormatError(f"line {line}: unsupported YAML ({s[0]!r}); use plain, quoted or [inline] values")
    s = _strip_comment(s)
    low = s.lower()
    if low in ("null", "~"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if _INT.match(s):
        return int(s)
    return s


def _closing_double(s: str, line: int) -> int:
    i = 1
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == '"':
            return i
        i += 1
    raise FormatError(f"line {line}: unterminated double-quoted string")


def _inline_list(raw: str, line: int) -> list:
    s = raw.strip()
    if not s.startswith("["):
        raise FormatError(f"line {line}: expected [inline list]")
    items, buf, i, depth_ok = [], "", 1, False
    while i < len(s):
        c = s[i]
        if c in "\"'":
            if c == '"':
                end = _closing_double(s[i:], line) + i
            else:
                end = s.find("'", i + 1)
                while end != -1 and end + 1 < len(s) and s[end + 1] == "'":
                    end = s.find("'", end + 2)
                if end == -1:
                    raise FormatError(f"line {line}: unterminated quote in list")
            buf += s[i : end + 1]
            i = end + 1
            continue
        if c == "[":
            raise FormatError(f"line {line}: nested lists are not supported")
        if c == ",":
            items.append(buf)
            buf = ""
        elif c == "]":
            items.append(buf)
            depth_ok = True
            rest = s[i + 1 :].strip()
            if rest and not rest.startswith("#"):
                raise FormatError(f"line {line}: text after ]: {rest!r}")
            break
        else:
            buf += c
        i += 1
    if not depth_ok:
        raise FormatError(f"line {line}: unterminated [inline list]")
    out = []
    for item in items:
        if item.strip() == "" and len(items) == 1:
            return []
        if item.strip() == "":
            raise FormatError(f"line {line}: empty item in list")
        out.append(_scalar(item, line))
    return out


def _value(raw: str | None, line: int):
    if raw is None:
        return None
    s = raw.strip()
    if s.startswith("["):
        return _inline_list(s, line)
    return _scalar(s, line)


def parse(src: str) -> dict:
    """Parse the subset into a dict. Raises FormatError with a line number."""
    lines = src.split("\n")
    data: dict = {}
    i = 0
    n = len(lines)

    def indent_of(text: str) -> int:
        return len(text) - len(text.lstrip(" "))

    while i < n:
        text = lines[i]
        lineno = i + 1
        if "\t" in text[: indent_of(text) + 1] and text.strip():
            raise FormatError(f"line {lineno}: tabs are not allowed for indentation")
        stripped = text.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if indent_of(text) != 0:
            raise FormatError(f"line {lineno}: unexpected indentation")
        m = _KEY.match(text)
        if not m:
            raise FormatError(f"line {lineno}: expected 'key: value'")
        key, raw = m.group(1), m.group(2)
        if key in data:
            raise FormatError(f"line {lineno}: duplicate key {key!r}")
        i += 1
        if raw is not None and raw.strip() and not raw.strip().startswith("#"):
            data[key] = _value(raw, lineno)
            continue
        # Block value: a list (possibly empty -> None).
        items: list = []
        while i < n:
            text = lines[i]
            lineno = i + 1
            stripped = text.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            ind = indent_of(text)
            if ind == 0:
                break
            if not stripped.startswith("- ") and stripped != "-":
                raise FormatError(f"line {lineno}: expected '- item' under {key!r}")
            body = stripped[1:].strip()
            item_indent = ind + 2
            i += 1
            km = _KEY.match(body)
            if km and not body.startswith(("'", '"')):
                mapping: dict = {}
                mapping[km.group(1)] = _value(km.group(2), lineno)
                while i < n:
                    text = lines[i]
                    lineno = i + 1
                    stripped = text.strip()
                    if not stripped or stripped.startswith("#"):
                        i += 1
                        continue
                    ind2 = indent_of(text)
                    if ind2 < item_indent:
                        break
                    if ind2 > item_indent:
                        raise FormatError(f"line {lineno}: nested mappings are not supported")
                    km2 = _KEY.match(stripped)
                    if not km2:
                        raise FormatError(f"line {lineno}: expected 'key: value' in list item")
                    if km2.group(1) in mapping:
                        raise FormatError(f"line {lineno}: duplicate key {km2.group(1)!r}")
                    if km2.group(2) is None:
                        raise FormatError(f"line {lineno}: nested blocks are not supported; use [inline] lists")
                    mapping[km2.group(1)] = _value(km2.group(2), lineno)
                    i += 1
                items.append(mapping)
            else:
                items.append(_value(body, lineno) if body else None)
        data[key] = items if items else None
    return data


def _dump_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if _PLAIN_SAFE.match(s) and s.lower() not in _RESERVED and not _INT.match(s) and not re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s
    return json.dumps(s, ensure_ascii=False)


def _dump_inline(items: list) -> str:
    return "[" + ", ".join(_dump_scalar(x) for x in items) + "]"


def dump(data: dict, order: list | None = None) -> str:
    """Serialise a dict in the subset. Keys in `order` come first, in that order."""
    keys = [k for k in (order or []) if k in data] + [k for k in data if k not in (order or [])]
    out = []
    for key in keys:
        v = data[key]
        if isinstance(v, dict):
            raise FormatError(f"{key}: nested mappings are not supported")
        if isinstance(v, list):
            if not v:
                out.append(f"{key}: []")
            elif all(isinstance(x, dict) for x in v):
                out.append(f"{key}:")
                for item in v:
                    first = True
                    for k2, v2 in item.items():
                        if isinstance(v2, dict):
                            raise FormatError(f"{key}.{k2}: nested mappings are not supported")
                        val = _dump_inline(v2) if isinstance(v2, list) else _dump_scalar(v2)
                        out.append(f"  {'- ' if first else '  '}{k2}: {val}")
                        first = False
            elif any(isinstance(x, (dict, list)) for x in v):
                raise FormatError(f"{key}: mix of mappings and scalars")
            else:
                inline = _dump_inline(v)
                if len(inline) + len(key) <= 100:
                    out.append(f"{key}: {inline}")
                else:
                    out.append(f"{key}:")
                    out.extend(f"  - {_dump_scalar(x)}" for x in v)
        else:
            out.append(f"{key}: {_dump_scalar(v)}")
    return "\n".join(out) + "\n"


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split '---\\n<yaml>\\n---\\n<body>' into (data, body)."""
    if not text.startswith("---\n") and text.strip() != "---":
        raise FormatError("line 1: file must start with '---'")
    lines = text.split("\n")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise FormatError("frontmatter is not closed with '---'") from None
    return parse("\n".join(lines[1:end])), "\n".join(lines[end + 1 :])


def join_frontmatter(data: dict, body: str, order: list | None = None) -> str:
    body = body if body.startswith("\n") else "\n" + body
    return "---\n" + dump(data, order) + "---" + body
