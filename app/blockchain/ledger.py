from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.blockchain.chain import Blockchain
from app.core.config import settings

_ledger: Blockchain | None = None
_snapshot: dict[str, Any] | None = None


def get_ledger() -> Blockchain:
    global _ledger
    if _ledger is None:
        path = Path(settings.chain_path)
        if path.exists():
            _ledger = Blockchain.load(path, settings.pow_difficulty)
        else:
            _ledger = Blockchain(difficulty=settings.pow_difficulty)
            persist()
    return _ledger


def persist() -> None:
    get_ledger().save(settings.chain_path)


def snapshot() -> None:
    global _snapshot
    _snapshot = json.loads(json.dumps(get_ledger().to_dict(), default=str))


def restore_snapshot() -> None:
    global _ledger, _snapshot
    if _snapshot is None:
        return
    from app.blockchain.chain import Block

    data = json.loads(json.dumps(_snapshot))
    bc = Blockchain.__new__(Blockchain)
    bc.difficulty = data.get("difficulty", settings.pow_difficulty)
    bc.chain = [Block.from_dict(b) for b in data["chain"]]
    bc.pending_transactions = list(data.get("pending_transactions", []))
    _ledger = bc
    persist()
