"""Minimaler BibTeX-Parser für die Library-App."""
import re


def parse_bibtex(text: str) -> dict:
    entries = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,([^@]*?)\n\}", text, re.DOTALL):
        ty, key, body = m.group(1), m.group(2), m.group(3)
        fields = {"type": ty, "_raw": m.group(0)}
        for fm in re.finditer(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", body):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        entries[key] = fields
    return entries
