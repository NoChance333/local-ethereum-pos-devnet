import os
import sys
import json
import time
import solcx
from web3 import Web3
from eth_account import Account

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print("=" * 60)
    print("Connecting to local Ethereum PoS Devnet (Geth EL)...")
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    if not w3.is_connected():
        raise ConnectionError("Could not connect to Geth at http://127.0.0.1:8545. Make sure devnet is running!")
    
    chain_id = w3.eth.chain_id
    current_block = w3.eth.block_number
    print(f"Connected successfully! Chain ID: {chain_id}, Current Block: {current_block}")
    
    # Deployer account (pre-funded in genesis)
    deployer_pk = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    account = Account.from_key(deployer_pk)
    balance_wei = w3.eth.get_balance(account.address)
    balance_eth = w3.from_wei(balance_wei, 'ether')
    print(f"Deployer Address: {account.address}")
    print(f"Deployer Balance: {balance_eth} ETH")
    
    # Compile Storage.sol
    contract_path = os.path.join(BASE_DIR, "Storage.sol")
    print(f"\nCompiling {contract_path}...")
    solcx.install_solc('0.8.20')
    compiled = solcx.compile_files(
        [contract_path],
        solc_version='0.8.20',
        output_values=['abi', 'bin']
    )
    contract_key = f"{contract_path}:Storage"
    if contract_key not in compiled:
        contract_key = [k for k in compiled.keys() if k.endswith(":Storage")][0]
        
    contract_interface = compiled[contract_key]
    abi = contract_interface['abi']
    bytecode = contract_interface['bin']
    print(f"Compiled successfully! Bytecode length: {len(bytecode)} bytes")
    
    # Deploy Contract
    print("\nDeploying Storage.sol to PoS Devnet...")
    Storage = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(account.address)
    
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', 1000000000)
    max_priority_fee = w3.to_wei(2, 'gwei')
    max_fee = base_fee * 2 + max_priority_fee
    
    deploy_txn = Storage.constructor().build_transaction({
        'chainId': chain_id,
        'from': account.address,
        'nonce': nonce,
        'gas': 1000000,
        'maxFeePerGas': max_fee,
        'maxPriorityFeePerGas': max_priority_fee,
    })
    
    signed_deploy_txn = w3.eth.account.sign_transaction(deploy_txn, private_key=deployer_pk)
    deploy_hash = w3.eth.send_raw_transaction(signed_deploy_txn.raw_transaction)
    print(f"Deploy transaction broadcasted! Tx Hash: {deploy_hash.hex()}")
    print("Waiting for transaction to be packaged into a PoS block...")
    
    t0 = time.time()
    deploy_receipt = w3.eth.wait_for_transaction_receipt(deploy_hash, timeout=120)
    elapsed = time.time() - t0
    
    contract_address = deploy_receipt.contractAddress
    print(f"\n[+] CONTRACT DEPLOYED SUCCESSFULLY in {elapsed:.2f}s!")
    print(f"Contract Address:   {contract_address}")
    print(f"Block Number:       {deploy_receipt.blockNumber}")
    print(f"Block Hash:         {deploy_receipt.blockHash.hex()}")
    print(f"Gas Used:           {deploy_receipt.gasUsed}")
    print(f"Status:             {deploy_receipt.status} (1 = Success)")
    
    # Interact with Contract
    storage_contract = w3.eth.contract(address=contract_address, abi=abi)
    
    # Initial read
    val_initial = storage_contract.functions.get().call()
    print(f"\nInitial Storage value (get()): {val_initial}")
    assert val_initial == 0, f"Expected 0, got {val_initial}"
    
    # Execute state change: set(42069)
    test_value = 42069
    print(f"\nExecuting state change: set({test_value})...")
    nonce = w3.eth.get_transaction_count(account.address)
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', 1000000000)
    max_fee = base_fee * 2 + max_priority_fee
    
    set_txn = storage_contract.functions.set(test_value).build_transaction({
        'chainId': chain_id,
        'from': account.address,
        'nonce': nonce,
        'gas': 200000,
        'maxFeePerGas': max_fee,
        'maxPriorityFeePerGas': max_priority_fee,
    })
    
    signed_set_txn = w3.eth.account.sign_transaction(set_txn, private_key=deployer_pk)
    set_hash = w3.eth.send_raw_transaction(signed_set_txn.raw_transaction)
    print(f"Set transaction broadcasted! Tx Hash: {set_hash.hex()}")
    print("Waiting for transaction to be packaged into a PoS block...")
    
    t0 = time.time()
    set_receipt = w3.eth.wait_for_transaction_receipt(set_hash, timeout=120)
    elapsed = time.time() - t0
    
    print(f"\n[+] STATE CHANGE TRANSACTION CONFIRMED in {elapsed:.2f}s!")
    print(f"Block Number:       {set_receipt.blockNumber}")
    print(f"Block Hash:         {set_receipt.blockHash.hex()}")
    print(f"Gas Used:           {set_receipt.gasUsed}")
    print(f"Status:             {set_receipt.status} (1 = Success)")
    
    # Verify updated state
    val_updated = storage_contract.functions.get().call()
    print(f"\nUpdated Storage value (get()): {val_updated}")
    assert val_updated == test_value, f"Expected {test_value}, got {val_updated}"
    print(f"[SUCCESS] Value correctly updated from {val_initial} to {val_updated}!")
    
    # Save receipt info
    summary = {
        "chainId": chain_id,
        "deployer": account.address,
        "contractAddress": contract_address,
        "deploymentTxHash": deploy_hash.hex(),
        "deploymentBlockNumber": deploy_receipt.blockNumber,
        "deploymentBlockHash": deploy_receipt.blockHash.hex(),
        "deploymentGasUsed": deploy_receipt.gasUsed,
        "setTxHash": set_hash.hex(),
        "setBlockNumber": set_receipt.blockNumber,
        "setGasUsed": set_receipt.gasUsed,
        "storedValue": val_updated
    }
    receipt_file = os.path.join(BASE_DIR, "deployment_receipt.json")
    with open(receipt_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved to {receipt_file}")
    print("=" * 60)

if __name__ == '__main__':
    main()
