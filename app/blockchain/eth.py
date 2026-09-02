from __future__ import annotations

from typing import Any

from app.blockchain.ledger import get_ledger, persist
from app.core.config import settings


def ethereum_available() -> bool:
    if settings.blockchain_mode != "ethereum":
        return False
    try:
        from web3 import Web3

        w3 = Web3(Web3.HTTPProvider(settings.ethereum_rpc))
        return bool(w3.is_connected())
    except Exception:
        return False


def mode_status() -> dict[str, Any]:
    return {
        "mode": settings.blockchain_mode,
        "python_ledger": True,
        "ethereum_connected": ethereum_available(),
        "contract_address": settings.contract_address or None,
        "note": "Local Python PoW ledger is always authoritative for this prototype unless Ethereum is connected.",
    }


def commit_event(tx: dict[str, Any]) -> dict[str, Any]:
    ledger = get_ledger()
    ledger.add_transaction(tx)
    block = ledger.mine_pending_transactions()
    persist()
    return {
        "tx_id": tx["tx_id"],
        "block_index": block.index,
        "block_hash": block.hash,
        "timestamp": block.timestamp,
        "previous_hash": block.previous_hash,
        "nonce": block.nonce,
    }
