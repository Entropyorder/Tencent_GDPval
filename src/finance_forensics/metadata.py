import json
import re
from pathlib import Path


class CollectorMetadata:
    def __init__(self, records=None):
        self.records = records or []

    @classmethod
    def load(cls, path):
        if not path or not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"collector metadata must be a JSON array: {path}")
        return cls(data)

    def for_file(self, path):
        match = re.match(r"^(\d+)_", Path(path).name)
        if not match:
            return {}
        index = int(match.group(1))
        if index < 1 or index > len(self.records):
            return {}
        record = self.records[index - 1]
        return record if isinstance(record, dict) else {}
