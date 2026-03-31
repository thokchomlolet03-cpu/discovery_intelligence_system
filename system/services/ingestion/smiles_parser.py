from __future__ import annotations

import io
import re

import pandas as pd


HEADER_HINTS = {"smiles", "smiles,id", "smiles\tid", "smiles name", "smiles\tname"}


def _decode_bytes(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="ignore")


def parse_smiles_text(file_bytes: bytes, filename: str = "") -> pd.DataFrame:
    text = _decode_bytes(file_bytes)
    stripped_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not stripped_lines:
        raise ValueError("The uploaded text file does not contain any molecule rows.")

    first_line = stripped_lines[0].lower()
    if any(token in first_line for token in HEADER_HINTS) or ("smiles" in first_line and ("\t" in first_line or "," in first_line)):
        try:
            return pd.read_csv(io.StringIO(text), sep=None, engine="python")
        except Exception:
            pass

    rows: list[dict[str, str]] = []
    for index, line in enumerate(stripped_lines):
        if line.startswith("#"):
            continue
        parts = re.split(r"[\t, ]+", line, maxsplit=1)
        smiles = parts[0].strip()
        entity_id = parts[1].strip() if len(parts) > 1 else f"molecule_{index + 1}"
        if not smiles:
            continue
        rows.append({"smiles": smiles, "entity_id": entity_id})

    if not rows:
        raise ValueError("The uploaded text file did not contain any usable SMILES entries.")
    return pd.DataFrame(rows)
