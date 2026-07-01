"""Source loaders.

Every loader returns a list of *reading records* — plain dicts with a uniform
shape so :mod:`hanzihub.merge` can concatenate them into the canonical long table:

    {
        "char":     str,   # single Han character
        "column":   str,   # wide-CSV column this reading belongs to (e.g. "Hokkien")
        "reading":  str,   # the reading text (clean; no source tags)
        "source":   str,   # provenance tag from hanzihub.schema (SRC_*)
        "locality": str,   # optional finer locality ("" if N/A), e.g. "Fuzhou"
        "conf":     float, # confidence in [0,1]; 1.0 for sourced data
    }
"""
from __future__ import annotations

import unicodedata
from typing import Any


def record(char: str, column: str, reading: str, source: str,
           locality: str = "", conf: float = 1.0) -> dict[str, Any]:
    return {
        "char": char,
        "column": column,
        "reading": unicodedata.normalize("NFC", str(reading)).strip(),
        "source": source,
        "locality": locality,
        "conf": float(conf),
    }


def is_single_han(ch: str) -> bool:
    """True if ``ch`` is exactly one CJK ideograph (incl. extensions A–)."""
    if not ch or len(ch) != 1:
        return False
    o = ord(ch)
    return (
        0x3400 <= o <= 0x9FFF
        or 0xF900 <= o <= 0xFAFF
        or 0x20000 <= o <= 0x3FFFF
    )
