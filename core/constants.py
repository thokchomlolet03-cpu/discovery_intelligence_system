from pathlib import Path


DESCRIPTOR_COLUMNS = ["mw", "rdkit_logp", "h_donors", "h_acceptors"]
FINGERPRINT_BITS = 2048
FINGERPRINT_COLUMNS = [f"fp_{idx}" for idx in range(FINGERPRINT_BITS)]

DATA_DIR = Path("data")
STRUCTURED_DATA_PATH = DATA_DIR / "data.csv"
ROOT_DATA_PATH = Path("data.csv")
KNOWLEDGE_PATH = DATA_DIR / "knowledge.json"
LOGS_PATH = DATA_DIR / "logs.json"
DECISION_OUTPUT_PATH = DATA_DIR / "decision_output.json"


def preferred_data_path():
    return STRUCTURED_DATA_PATH if STRUCTURED_DATA_PATH.exists() else ROOT_DATA_PATH
