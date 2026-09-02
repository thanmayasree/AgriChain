from __future__ import annotations

import hashlib
import json
import time
from typing import Any


class Block:
    def __init__(
        self,
        index: int,
        transactions: list[dict[str, Any]],
        previous_hash: str,
        timestamp: float | None = None,
        nonce: int = 0,
        hash: str | None = None,
    ) -> None:
        self.index = index
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = hash if hash is not None else self.compute_hash()

    def compute_hash(self) -> str:
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "transactions": self.transactions,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty: int) -> None:
        target = "0" * difficulty
        self.hash = self.compute_hash()
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": json.loads(json.dumps(self.transactions, default=str)),
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Block":
        return cls(
            index=d["index"],
            transactions=d["transactions"],
            previous_hash=d["previous_hash"],
            timestamp=d["timestamp"],
            nonce=d["nonce"],
            hash=d["hash"],
        )


class Blockchain:
    GENESIS_PREVIOUS_HASH = "0"

    def __init__(self, difficulty: int = 2) -> None:
        self.difficulty = difficulty
        self.chain: list[Block] = []
        self.pending_transactions: list[dict[str, Any]] = []
        self.create_genesis_block()

    def create_genesis_block(self) -> None:
        genesis = Block(0, [], self.GENESIS_PREVIOUS_HASH)
        genesis.mine_block(self.difficulty)
        self.chain = [genesis]
        self.pending_transactions = []

    def get_latest_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, transaction: dict[str, Any]) -> None:
        self.pending_transactions.append(transaction)

    def mine_pending_transactions(self) -> Block:
        block = Block(
            index=len(self.chain),
            transactions=list(self.pending_transactions),
            previous_hash=self.get_latest_block().hash,
        )
        block.mine_block(self.difficulty)
        self.chain.append(block)
        self.pending_transactions = []
        return block

    def is_chain_valid(self) -> tuple[bool, str | None, int | None]:
        genesis = self.chain[0]
        if genesis.hash != genesis.compute_hash():
            return False, "Genesis hash mismatch", 0
        if genesis.previous_hash != self.GENESIS_PREVIOUS_HASH:
            return False, "Genesis previous hash invalid", 0
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False, "Block content hash mismatch", current.index
            if current.previous_hash != previous.hash:
                return False, "Broken previous-hash link", current.index
        return True, None, None

    def find_tamper(self) -> dict[str, Any]:
        valid, reason, index = self.is_chain_valid()
        return {"valid": valid, "reason": reason, "failed_block": index}

    def get_batch_history(self, batch_id: str) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("batch_id") == batch_id:
                    history.append(
                        {
                            "block_index": block.index,
                            "block_hash": block.hash,
                            "timestamp": block.timestamp,
                            "transaction": tx,
                        }
                    )
        return history

    def to_dict(self) -> dict[str, Any]:
        return {
            "difficulty": self.difficulty,
            "chain": [b.to_dict() for b in self.chain],
            "pending_transactions": self.pending_transactions,
        }

    def save(self, path) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path, difficulty: int = 2) -> "Blockchain":
        with open(path) as f:
            data = json.load(f)
        bc = cls.__new__(cls)
        bc.difficulty = data.get("difficulty", difficulty)
        bc.chain = [Block.from_dict(b) for b in data["chain"]]
        bc.pending_transactions = data.get("pending_transactions", [])
        return bc
