from pathlib import Path
import json

DATA_DIR = Path(__file__).resolve().parent / "data"


def load_json(name: str) -> list:
    return json.loads((DATA_DIR / name).read_text())
