"""In-process log of flag decisions."""

from __future__ import annotations


class AuditLog:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, flag: str, subject: str, enabled: bool, reason: str) -> None:
        # Append one decision
        self.events.append(
            {
                "flag": flag,
                "subject": subject,
                "enabled": enabled,
                "reason": reason,
            }
        )
