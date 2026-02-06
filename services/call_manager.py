from datetime import datetime, timezone


class CallManager:
    """In-memory conversation state for active calls."""

    def __init__(self):
        # call_sid -> list of {"role": str, "content": str, "timestamp": str}
        self._conversations: dict[str, list[dict]] = {}

    def start_call(self, call_sid: str):
        self._conversations[call_sid] = []

    def add_turn(self, call_sid: str, role: str, content: str):
        if call_sid not in self._conversations:
            self.start_call(call_sid)
        self._conversations[call_sid].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_history(self, call_sid: str) -> list[dict]:
        return self._conversations.get(call_sid, [])

    def get_openai_messages(self, call_sid: str) -> list[dict]:
        """Convert conversation history to OpenAI chat format."""
        messages = []
        for turn in self.get_history(call_sid):
            if turn["role"] == "caller":
                messages.append({"role": "user", "content": turn["content"]})
            else:
                messages.append({"role": "assistant", "content": turn["content"]})
        return messages

    def end_call(self, call_sid: str) -> list[dict]:
        """End a call and return its transcript."""
        return self._conversations.pop(call_sid, [])

    def get_active_call_sids(self) -> list[str]:
        return list(self._conversations.keys())


# Singleton instance
call_manager = CallManager()
