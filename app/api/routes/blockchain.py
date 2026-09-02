from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.blockchain.eth import mode_status
from app.blockchain.ledger import get_ledger, persist, restore_snapshot, snapshot
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.config import ROOT
from app.models.entities import User

router = APIRouter()

_original_qty: dict[str, float] = {}


@router.get("/blockchain")
def blockchain_status(_=Depends(get_current_user)):
    ledger = get_ledger()
    valid, reason, failed = ledger.is_chain_valid()
    latest = ledger.get_latest_block()
    return {
        "chain_status": "VALID" if valid else "COMPROMISED",
        "integrity": valid,
        "reason": reason,
        "failed_block": failed,
        "block_height": latest.index,
        "latest_hash": latest.hash,
        "latest_block": latest.index,
        "network_status": "LOCAL_POW",
        "pending": len(ledger.pending_transactions),
        "mode": mode_status(),
        "blocks": [b.to_dict() for b in ledger.chain],
    }


@router.get("/blockchain/verify")
def verify_chain(_=Depends(get_current_user)):
    valid, reason, failed = get_ledger().is_chain_valid()
    return {
        "valid": valid,
        "message": "Blockchain integrity verified" if valid else "INTEGRITY COMPROMISED",
        "reason": reason,
        "failed_block": failed,
    }


@router.get("/blocks/{index}")
def get_block(index: int, _=Depends(get_current_user)):
    ledger = get_ledger()
    if index < 0 or index >= len(ledger.chain):
        raise HTTPException(404, "Block not found")
    return ledger.chain[index].to_dict()


@router.post("/debug/tamper")
def tamper(batch_id: str = "RICE-KONASEEMA-2026-0001", _=Depends(require_roles("ADMIN", "REGULATOR"))):
    ledger = get_ledger()
    snapshot()
    for block in ledger.chain:
        for tx in block.transactions:
            if tx.get("batch_id") == batch_id:
                meta = tx.get("metadata") or {}
                if "quantity_kg" in meta:
                    _original_qty[batch_id] = meta["quantity_kg"]
                    meta["quantity_kg"] = 9999
                    tx["metadata"] = meta
                    persist()
                    valid, reason, failed = ledger.is_chain_valid()
                    return {
                        "message": "Simulated tampering: 2500 kg → 9999 kg",
                        "valid": valid,
                        "reason": reason,
                        "failed_block": failed,
                    }
                if "quantity_kg" in tx:
                    tx["quantity_kg"] = 9999
                    persist()
                    valid, reason, failed = ledger.is_chain_valid()
                    return {
                        "message": "Simulated tampering",
                        "valid": valid,
                        "reason": reason,
                        "failed_block": failed,
                    }
    # mutate first non-genesis transaction payload to guarantee break
    if len(ledger.chain) > 1 and ledger.chain[1].transactions:
        ledger.chain[1].transactions[0]["tampered"] = True
        persist()
        valid, reason, failed = ledger.is_chain_valid()
        return {"message": "Simulated tampering on block 1", "valid": valid, "reason": reason, "failed_block": failed}
    raise HTTPException(400, "No transaction found to tamper")


@router.post("/debug/restore")
def restore(_=Depends(require_roles("ADMIN", "REGULATOR"))):
    restore_snapshot()
    valid, reason, failed = get_ledger().is_chain_valid()
    return {"restored": True, "valid": valid, "reason": reason, "failed_block": failed}


@router.get("/smart-contracts")
def contracts():
    sol = (ROOT / "contracts" / "AgriChain.sol").read_text() if (ROOT / "contracts" / "AgriChain.sol").exists() else ""
    return {"mode": mode_status(), "solidity_preview": sol[:4000]}
