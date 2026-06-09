from collections import defaultdict
from typing import List, Dict


class ConversationService:
    """
    Stores conversation history per phone number, in memory.
    Each phone number gets its own list of message dicts.

    Week 2 uses in-memory storage — good enough for testing.
    Week 3 will move this to a database so history survives restarts.
    """

    def __init__(self, max_history: int = 10):
        # defaultdict means we never get a KeyError for a new phone number
        self._store: Dict[str, List[Dict]] = defaultdict(list)
        self.max_history = max_history

    def add_message(self, phone: str, role: str, content: str):
        """
        role must be 'user' or 'assistant'.
        Keeps only the last max_history messages per phone.
        """
        self._store[phone].append({"role": role, "content": content})

        # Trim to max_history to avoid sending huge prompts to Gemini
        if len(self._store[phone]) > self.max_history:
            self._store[phone] = self._store[phone][-self.max_history:]

    def get_history(self, phone: str) -> List[Dict]:
        return self._store[phone].copy()

    def clear(self, phone: str):
        """Let users reset their conversation by sending 'reset'."""
        self._store[phone] = []