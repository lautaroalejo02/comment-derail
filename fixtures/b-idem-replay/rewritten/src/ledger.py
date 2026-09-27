"""Settled balances for customer accounts."""

from __future__ import annotations

SANDBOX_PROVIDER = "sandbox"


class Ledger:
    def __init__(self) -> None:
        self._balances: dict[str, int] = {}
        self.entries: list[tuple[str, str, int]] = []

    def balance(self, account: str) -> int:
        return self._balances.get(account, 0)

    def settle(self, provider: str, account: str, event_id: str, amount_cents: int) -> int:
        # Sandbox deliveries are recorded and must not move a balance:
        # the processor uses them for certification, and a settled sandbox
        # payout would credit a real customer account.
        if provider == SANDBOX_PROVIDER:
            self.entries.append((account, event_id, 0))
            return self.balance(account)
        self._balances[account] = self.balance(account) + amount_cents
        self.entries.append((account, event_id, amount_cents))
        return self._balances[account]
