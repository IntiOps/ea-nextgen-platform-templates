from typing import Protocol


class MessageSender(Protocol):
    def send(self, to: str, message: str) -> None: ...
