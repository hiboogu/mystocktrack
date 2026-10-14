"""In-process message bus: every message between agents is recorded in one transcript."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

BROADCAST = "*"


@dataclass(frozen=True)
class Message:
    sender: str
    recipient: str
    kind: str  # task | report | challenge | rebuttal | risk_assessment | decision
    content: str
    payload: dict = field(default_factory=dict)
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class MessageBus:
    def __init__(self) -> None:
        self.transcript: list[Message] = []

    def send(self, sender: str, recipient: str, kind: str, content: str, **payload) -> Message:
        msg = Message(sender, recipient, kind, content, payload)
        self.transcript.append(msg)
        return msg

    def inbox(self, recipient: str, kind: str | None = None) -> list[Message]:
        return [
            m
            for m in self.transcript
            if m.recipient in (recipient, BROADCAST) and (kind is None or m.kind == kind)
        ]
