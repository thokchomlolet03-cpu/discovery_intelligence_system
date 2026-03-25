import json
from pathlib import Path

from core.constants import KNOWLEDGE_PATH


def load_knowledge(path=KNOWLEDGE_PATH):
    target = Path(path)
    if not target.exists():
        return []
    with open(target, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, list) else []


def save_knowledge(entry, path=KNOWLEDGE_PATH):
    target = Path(path)
    knowledge = load_knowledge(target)
    knowledge.append(entry)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(knowledge, handle, indent=2)


def save_knowledge_entries(entries, path=KNOWLEDGE_PATH):
    target = Path(path)
    knowledge = load_knowledge(target)
    knowledge.extend(entries)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(knowledge, handle, indent=2)

