import json
from pathlib import Path


ENGLISH = json.loads(Path(__file__).with_name("lang").joinpath("en.json").read_text(encoding="utf-8"))
