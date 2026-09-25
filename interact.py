import os
import sys
import json
from web3 import Web3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECEIPT_PATH = os.path.join(BASE_DIR, "deployment_receipt.json")

STORAGE_ABI = [
    {
        "inputs": [],
        "name": "get",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "_value", "type": "uint256"}],
        "name": "set",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [{"indexed": False, "internalType": "uint256", "name": "newValue", "type": "uint256"}],
        "name": "ValueChanged",
        "type": "event"
    }
]

def main():
    print("=" * 60)
    print("Connecting to local Ethereum node...")
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

    if not w3.is_connected():
        print("ERROR: Cannot connect to node at http://127.0.0.1:8545.")
        print("Make sure your node is running in Terminal 1 (python run_ondemand.py).")
        sys.exit(1)

    if not os.path.exists(RECEIPT_PATH):
        print("ERROR: No deployment_receipt.json found. Run 'python deploy_and_verify.py' first.")
        sys.exit(1)

    with open(RECEIPT_PATH, "r") as f:
        receipt = json.load(f)

    contract_addr = receipt.get("contractAddress")
    print(f"Connected! Current Block: {w3.eth.block_number}")
    print(f"Target Contract: {contract_addr}")

    code = w3.eth.get_code(contract_addr)
    if len(code) == 0:
        print(f"ERROR: No contract bytecode found at {contract_addr}! (Chain may have been reset).")
        sys.exit(1)

    contract = w3.eth.contract(address=contract_addr, abi=STORAGE_ABI)
    current_val = contract.functions.get().call()
    print(f"Current Value stored in contract: {current_val}")

    # If user provided a new value argument: python interact.py <new_val>
    if len(sys.argv) > 1:
        try:
            new_val = int(sys.argv[1])
        except ValueError:
            print("Usage: python interact.py [number]")
            return

        print(f"\nSending transaction to update value to: {new_val}...")
        priv = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        acct = w3.eth.account.from_key(priv)

        tx = contract.functions.set(new_val).build_transaction({
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 100000,
            "gasPrice": w3.eth.gas_price,
            "chainId": 12345
        })

        signed = w3.eth.account.sign_transaction(tx, priv)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Tx Broadcasted! Hash: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        print(f"Confirmed in Block #{tx_receipt.blockNumber} (Status: {tx_receipt.status})")

        updated_val = contract.functions.get().call()
        print(f"Updated Value stored in contract: {updated_val}")
    else:
        print("\nTip: To update the value, run: python interact.py <number>")
        print("Example: python interact.py 8888")

    print("=" * 60)

if __name__ == '__main__':
    main()
