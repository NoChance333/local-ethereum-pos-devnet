# 🚀 Local Ethereum Proof-of-Stake (PoS) Devnet (Native Windows)

A complete, turnkey, and fully functional private local **Ethereum Proof-of-Stake (PoS) Devnet** running natively on **Windows** using **Geth** as the Execution Layer (EL) and **Prysm** as the Consensus Layer (CL).

---

## 📌 Why this repository?

Setting up a local Ethereum devnet post-Merge has become notoriously difficult, especially for Windows developers. Most existing guides assume Linux or Docker, and developers regularly run into blocking issues such as:

1. ❌ **Engine API (Auth RPC) Failures:** Improper JWT secret configuration between Geth and Beacon node.
2. ❌ **Geth `blobSchedule` Rejections:** Modern Geth (v1.14+) fails to initialize custom genesis unless `cancun` and `prague` blob schedules are configured.
3. ❌ **Deprecated Interop Flags in Prysm:** Newer Prysm versions removed `--interop-num-validators`, causing the validator client to crash without an explicit EIP-2335 keystore wallet.
4. ❌ **Slot Timing & Future Block Rejections:** Mismatches between consensus slot duration (`SECONDS_PER_SLOT: 12`) and block proposal timing.

**This repository solves all of these problems.** It includes automated scripts to download required binaries, configure consensus & execution genesis, generate matching 64 deterministic validator keys, supervise node execution, and verify deployment with a Solidity smart contract.

---

## 🏛️ Architecture

```
+-------------------------------------------------------------------------+
|                              LOCAL MACHINE                              |
|                                                                         |
|  +--------------------+        Engine API (Auth RPC)        +--------+  |
|  |    Geth (EL)       | <=================================> | Prysm  |  |
|  | http://127.0.0.1   |      Port 8551 (via jwt.hex)        | Beacon |  |
|  |   RPC: 8545        |                                     | Node   |  |
|  +--------------------+                                     | (CL)   |  |
|            ^                                                +--------+  |
|            | JSON-RPC (eth_sendRawTransaction)                   ^      |
|            |                                            gRPC:4000|      |
|  +--------------------+                                     v        |  |
|  | Smart Contract /   |                             +----------------+  |
|  | dApp / deploy script|                            | Prysm Validator|  |
|  +--------------------+                             | (64 keys)      |  |
|                                                     +----------------+  |
+-------------------------------------------------------------------------+
```

---

## ⚙️ Prerequisites

1. **Operating System:** Windows 10 / 11 (64-bit)
2. **Python:** Python 3.10+ installed and added to `PATH`
3. **PowerShell:** Standard Windows PowerShell
4. **Geth:** Download `geth.exe` for Windows from the [Official Geth Downloads](https://geth.ethereum.org/downloads) (or place `geth.exe` directly in this folder).

---

## 🚀 Quickstart (Automated Setup)

### 1. Clone the repository
```bash
git clone https://github.com/NoChance333/local-ethereum-pos-devnet.git
cd local-ethereum-pos-devnet
```

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Download Prysm Binaries
Run the included multi-threaded parallel downloader to fetch matching Windows binaries for `prysmctl.exe`, `beacon-chain.exe`, and `validator.exe`:
```bash
python downloader.py
```
*(Ensure `geth.exe` is also placed in the project folder.)*

### 4. Choose Your Running Mode

#### ⚡ Mode A: Instant On-Demand Node (Recommended for Fast Smart Contract & dApp Dev)
No empty auto-blocks, 0 terminal spam, blocks are mined instantly (<0.1s) only when transactions arrive:
```bash
python run_ondemand.py
```
*(If you ever want to wipe data and start fresh from block 0, run: `python run_ondemand.py --reset`)*

#### 🛡️ Mode B: Full Ethereum PoS Devnet (Geth + Prysm Beacon + 64 Validators)
Simulates real Ethereum Proof-of-Stake with full Beacon consensus and 12-second slot proposing:
```bash
python -u run_devnet.py
```
*(To wipe and re-align genesis slot to current time: `python -u run_devnet.py --reset`)*

### 5. Deploy Smart Contract
In a second terminal:
```bash
python deploy_and_verify.py
```
This compiles `Storage.sol`, deploys it to the network, sets the value to `42069`, verifies `get()`, and saves the deployed address to `deployment_receipt.json`.

### 6. Interact With Existing Deployed Contract
You don't need to re-deploy the contract each time you want to test it! Run:
```bash
# Read current value from contract
python interact.py

# Send a transaction to update value (e.g., set to 8888)
python interact.py 8888
```

---

## 🖥️ Manual Setup (Running in Separate VS Code Terminals)

If you prefer to see each process logging in its own separate terminal tab in VS Code:

### Terminal 1: Geth Execution Layer
```powershell
.\geth.exe --datadir ./geth-data --networkid 12345 --http --http.api eth,net,web3,personal,engine --http.port 8545 --http.addr 127.0.0.1 --http.corsdomain * --authrpc.port 8551 --authrpc.jwtsecret ./jwt.hex --authrpc.addr 127.0.0.1 --authrpc.vhosts * --nodiscover --syncmode full
```

### Terminal 2: Prysm Beacon Node
```powershell
.\beacon-chain.exe --datadir ./beacon-data --genesis-state ./genesis.ssz --chain-config-file ./config.yaml --execution-endpoint http://127.0.0.1:8551 --jwt-secret ./jwt.hex --accept-terms-of-use --min-sync-peers 0 --contract-deployment-block 0 --rpc-host 127.0.0.1 --rpc-port 4000 --grpc-gateway-host 127.0.0.1 --grpc-gateway-port 3500 --p2p-tcp-port 13000 --p2p-udp-port 12000 --suggested-fee-recipient 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 --disable-staking-contract-check --subscribe-all-subnets --minimum-peers-per-subnet 0
```

### Terminal 3: Prysm Validator Client
```powershell
.\validator.exe --wallet-dir ./validator-wallet --wallet-password-file ./wallet_pass.txt --beacon-rpc-provider 127.0.0.1:4000 --chain-config-file ./config.yaml --accept-terms-of-use --suggested-fee-recipient 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
```

### Terminal 4: Test & Interaction
```powershell
# Deploy test smart contract
python deploy_and_verify.py

# Query current block number
curl.exe -X POST http://127.0.0.1:8545 -H "Content-Type: application/json" -d '{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}'

# Query beacon head slot
curl.exe -s http://127.0.0.1:3500/eth/v1/beacon/headers/head
```

---

## 🛑 Stopping the Devnet

To cleanly stop all background Geth, Beacon, and Validator processes:
```powershell
powershell -ExecutionPolicy Bypass -File .\stop_devnet.ps1
```

---

## 🔑 Pre-Funded Test Accounts

The genesis file pre-funds standard development accounts with ample ETH:

| Account | Address | Private Key |
| :--- | :--- | :--- |
| **Account 0** | `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` | `0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80` |
| **Account 1** | `0xfe3b557e8fb62b89f4916b721be55ceb828dbd73` | `0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d` |

### 🦊 Connecting to MetaMask
- **Network Name:** Local PoS Devnet
- **New RPC URL:** `http://127.0.0.1:8545`
- **Chain ID:** `12345`
- **Currency Symbol:** `ETH`

---

## 📁 Repository Structure

```
├── config.yaml                   # Consensus chain config (Deneb fork, 12s slots)
├── genesis_in.json               # Execution genesis template with blob schedules
├── keygen_test_vector.yaml       # Official interop deterministic validator keys
├── Storage.sol                   # Test smart contract (get / set)
├── downloader.py                 # Multi-threaded parallel downloader for Prysm
├── generate_validator_wallet.py  # Generates & imports 64 matching validator keys
├── run_devnet.py                 # Automated devnet supervisor & monitoring loop
├── start_devnet.ps1              # PowerShell script to launch nodes in background
├── stop_devnet.ps1               # Clean shutdown script for all nodes
├── deploy_and_verify.py          # Contract compilation, deployment, and verification
├── requirements.txt              # Python requirements
└── README.md                     # Documentation
```

---

## 📜 License

MIT License. Feel free to use, modify, and share!
