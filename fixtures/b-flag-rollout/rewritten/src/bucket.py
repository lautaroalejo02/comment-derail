"""Stable rollout bucket for a subject id."""

from __future__ import annotations


def bucket_for(subject: str) -> int:
    total = 0
    for ch in subject:
        total = (total * 33 + ord(ch)) % 100
    return total
