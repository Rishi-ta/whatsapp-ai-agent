import json
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)
HISTORY_FILE = Path("data/conversations.json")


class ConversationService:
    def __init__(self, max_history: int = 10):
        self.max_history = max_history

    def _load(self) -> Dict:
        if not HISTORY_FILE.exists():
            return {}
        with open(HISTORY_FILE) as f:
            return json.load(f)

    def _save(self, data: Dict):
        HISTORY_FILE.parent.mkdir(exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def add_message(self, phone: str, role: str, content: str):
        data = self._load()
        if phone not in data:
            data[phone] = []
        data[phone].append({"role": role, "content": content})
        # Keep only last max_history messages
        data[phone] = data[phone][-self.max_history:]
        self._save(data)

    def get_history(self, phone: str) -> List[Dict]:
        data = self._load()
        return data.get(phone, [])

    def clear(self, phone: str):
        data = self._load()
        data[phone] = []
        self._save(data)