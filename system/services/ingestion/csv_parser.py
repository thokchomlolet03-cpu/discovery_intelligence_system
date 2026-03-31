from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd


def _decode_bytes(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="ignore")


def _sniff_delimiter(text: str, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".tsv":
        return "\t"
    sample = "\n".join(text.splitlines()[:20]).strip()
    if not sample:
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return ","


def parse_tabular_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    text = _decode_bytes(file_bytes)
    delimiter = _sniff_delimiter(text, filename)
    return pd.read_csv(io.StringIO(text), sep=delimiter)
