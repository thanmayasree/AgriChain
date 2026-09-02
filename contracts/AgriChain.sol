pragma solidity ^0.8.20;

/// @title AgriChain — optional Ethereum anchor for batch events
/// @notice The hackathon prototype runs a Python PoW ledger by default.
///         Deploy this contract on Hardhat/Ganache and set BLOCKCHAIN_MODE=ethereum.
contract AgriChain {
    struct SupplyEvent {
        string batchId;
        string eventType;
        string actor;
        string dataHash;
        uint256 timestamp;
        string location;
    }

    mapping(string => SupplyEvent[]) private eventsByBatch;
    mapping(string => bool) public registered;
    address public owner;

    event BatchRegistered(string batchId, address indexed registrar);
    event EventRecorded(string batchId, string eventType, string dataHash, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function registerBatch(string calldata batchId) external {
        require(!registered[batchId], "exists");
        registered[batchId] = true;
        emit BatchRegistered(batchId, msg.sender);
    }

    function addSupplyChainEvent(
        string calldata batchId,
        string calldata eventType,
        string calldata actor,
        string calldata dataHash,
        string calldata location
    ) external {
        require(registered[batchId], "unknown batch");
        eventsByBatch[batchId].push(
            SupplyEvent(batchId, eventType, actor, dataHash, block.timestamp, location)
        );
        emit EventRecorded(batchId, eventType, dataHash, block.timestamp);
    }

    function storeDataHash(
        string calldata batchId,
        string calldata dataHash
    ) external {
        require(registered[batchId], "unknown batch");
        eventsByBatch[batchId].push(
            SupplyEvent(batchId, "HASH", msg.sender == owner ? "owner" : "actor", dataHash, block.timestamp, "")
        );
    }

    function getEvents(string calldata batchId) external view returns (SupplyEvent[] memory) {
        return eventsByBatch[batchId];
    }

    function verifyBatch(string calldata batchId) external view returns (bool ok, uint256 eventCount) {
        ok = registered[batchId];
        eventCount = eventsByBatch[batchId].length;
    }
}
