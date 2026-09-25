import os
import sys
import time
import secrets
import subprocess
import json
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def check_rpc():
    try:
        req = urllib.request.Request("http://127.0.0.1:8545", data=json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.load(resp)
            return int(data["result"], 16)
    except Exception:
        return None

def check_beacon():
    try:
        req = urllib.request.Request("http://127.0.0.1:3500/eth/v1/beacon/headers/head")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.load(resp)
            header = data.get("data", {}).get("header", {}).get("message", {})
            return header.get("slot"), header.get("proposer_index")
    except Exception:
        return None, None

def ensure_jwt(jwt_path):
    if not os.path.exists(jwt_path):
        token = secrets.token_hex(32)
        with open(jwt_path, "w") as f:
            f.write(token)
        print(f"Generated new JWT secret at {jwt_path}")

def ensure_wallet():
    wallet_dir = os.path.join(BASE_DIR, "validator-wallet")
    if not os.path.exists(wallet_dir) or not os.listdir(wallet_dir):
        print("Validator wallet not found. Generating 64 validator keys...")
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_validator_wallet.py")], check=True)

def main():
    print("=" * 60)
    print("Starting Local Ethereum PoS Devnet Supervisor...")
    print(f"Working Directory: {BASE_DIR}")
    print("=" * 60)

    # 1. Stop any running processes
    print("Stopping any existing processes...")
    stop_script = os.path.join(BASE_DIR, "stop_devnet.ps1")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", stop_script], capture_output=True)
    time.sleep(1)

    # 2. Check binaries
    geth_exe = os.path.join(BASE_DIR, "geth.exe")
    prysmctl_exe = os.path.join(BASE_DIR, "prysmctl.exe")
    beacon_exe = os.path.join(BASE_DIR, "beacon-chain.exe")
    val_exe = os.path.join(BASE_DIR, "validator.exe")

    for exe_name, exe_path in [("Geth", geth_exe), ("Prysmctl", prysmctl_exe), ("Beacon Node", beacon_exe), ("Validator", val_exe)]:
        if not os.path.exists(exe_path):
            print(f"ERROR: {exe_name} binary not found at {exe_path}!")
            print("Please run 'python downloader.py' to download the Prysm binaries, and ensure geth.exe is present.")
            sys.exit(1)

    # 3. Setup JWT and Wallet
    jwt_file = os.path.join(BASE_DIR, "jwt.hex")
    ensure_jwt(jwt_file)
    ensure_wallet()

    geth_data = os.path.join(BASE_DIR, "geth-data")
    beacon_data = os.path.join(BASE_DIR, "beacon-data")
    val_data = os.path.join(BASE_DIR, "validator-data")
    reset_mode = "--reset" in sys.argv

    # 4. Handle persistence vs clean reset
    if reset_mode:
        print("Reset flag detected. Cleaning execution, beacon & validator databases for fresh genesis...")
        for p in [geth_data, beacon_data, val_data]:
            if os.path.exists(p):
                subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{p}'"], capture_output=True)
        appdata_eth2 = os.path.expandvars(r"%LOCALAPPDATA%\Eth2\validator.db")
        if os.path.exists(appdata_eth2):
            try:
                os.remove(appdata_eth2)
            except Exception:
                pass

    logs_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    config_yaml = os.path.join(BASE_DIR, "config.yaml")
    genesis_ssz = os.path.join(BASE_DIR, "genesis.ssz")
    genesis_in = os.path.join(BASE_DIR, "genesis_in.json")
    genesis_out = os.path.join(BASE_DIR, "genesis.json")

    needs_genesis = reset_mode or (not os.path.exists(geth_data)) or (not os.path.exists(beacon_data))

    if needs_genesis:
        # 5. Generate Genesis
        print("Generating Beacon & Geth PoS Genesis (with 12s delay)...")
        cmd_genesis = [
            prysmctl_exe, "testnet", "generate-genesis",
            "--fork=deneb",
            f"--chain-config-file={config_yaml}",
            "--num-validators=64",
            f"--output-ssz={genesis_ssz}",
            f"--geth-genesis-json-in={genesis_in}",
            f"--geth-genesis-json-out={genesis_out}",
            "--genesis-time-delay=12"
        ]
        res = subprocess.run(cmd_genesis, capture_output=True, text=True)
        if res.returncode != 0:
            print("Genesis generation failed:\n", res.stderr)
            sys.exit(1)
        print("Genesis files created successfully.")

        # 6. Initialize Geth
        print("Initializing Geth with custom genesis...")
        cmd_geth_init = [geth_exe, "--datadir", geth_data, "init", genesis_out]
        res2 = subprocess.run(cmd_geth_init, capture_output=True, text=True)
        if res2.returncode != 0:
            print("Geth initialization failed:\n", res2.stderr)
            sys.exit(1)
    else:
        print("Existing blockchain databases found! Resuming previous state (contracts & history preserved)...")
        print("Tip: Use 'python run_devnet.py --reset' if you ever want to wipe and start from block 0.")

    f_geth = open(os.path.join(logs_dir, "geth.log"), "w")
    f_beacon = open(os.path.join(logs_dir, "beacon.log"), "w")
    f_val = open(os.path.join(logs_dir, "validator.log"), "w")

    # 7. Start Geth
    print("Starting Geth Execution Layer (HTTP: 8545, Auth Engine: 8551)...")
    cmd_geth = [
        geth_exe,
        "--datadir", geth_data,
        "--networkid", "12345",
        "--http",
        "--http.api", "eth,net,web3,personal,engine",
        "--http.port", "8545",
        "--http.addr", "127.0.0.1",
        "--http.corsdomain", "*",
        "--authrpc.port", "8551",
        "--authrpc.jwtsecret", jwt_file,
        "--authrpc.addr", "127.0.0.1",
        "--authrpc.vhosts", "*",
        "--nodiscover",
        "--syncmode", "full",
        "--gcmode", "archive"
    ]
    p_geth = subprocess.Popen(cmd_geth, stdout=f_geth, stderr=subprocess.STDOUT)
    time.sleep(2)

    # 8. Start Beacon Node
    print("Starting Prysm Beacon Node (gRPC: 4000, REST: 3500)...")
    beacon_data = os.path.join(BASE_DIR, "beacon-data")
    cmd_beacon = [
        beacon_exe,
        "--datadir", beacon_data,
        "--genesis-state", genesis_ssz,
        "--chain-config-file", config_yaml,
        "--execution-endpoint", "http://127.0.0.1:8551",
        "--jwt-secret", jwt_file,
        "--accept-terms-of-use",
        "--min-sync-peers", "0",
        "--contract-deployment-block", "0",
        "--rpc-host", "127.0.0.1",
        "--rpc-port", "4000",
        "--grpc-gateway-host", "127.0.0.1",
        "--grpc-gateway-port", "3500",
        "--p2p-tcp-port", "13000",
        "--p2p-udp-port", "12000",
        "--suggested-fee-recipient", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "--disable-staking-contract-check",
        "--subscribe-all-subnets",
        "--minimum-peers-per-subnet", "0"
    ]
    p_beacon = subprocess.Popen(cmd_beacon, stdout=f_beacon, stderr=subprocess.STDOUT)
    time.sleep(2)

    # 9. Start Validator Client
    print("Starting Prysm Validator Client (64 active validators)...")
    wallet_dir = os.path.join(BASE_DIR, "validator-wallet")
    pwd_file = os.path.join(BASE_DIR, "wallet_pass.txt")
    cmd_val = [
        val_exe,
        "--datadir", val_data,
        "--wallet-dir", wallet_dir,
        "--wallet-password-file", pwd_file,
        "--beacon-rpc-provider", "127.0.0.1:4000",
        "--chain-config-file", config_yaml,
        "--accept-terms-of-use",
        "--suggested-fee-recipient", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    ]
    p_val = subprocess.Popen(cmd_val, stdout=f_val, stderr=subprocess.STDOUT)

    print("=" * 60)
    print(f"Devnet running! PIDs: Geth={p_geth.pid}, Beacon={p_beacon.pid}, Validator={p_val.pid}")
    print("Log files are being written to:")
    print(f"  Geth:      {os.path.join(logs_dir, 'geth.log')}")
    print(f"  Beacon:    {os.path.join(logs_dir, 'beacon.log')}")
    print(f"  Validator: {os.path.join(logs_dir, 'validator.log')}")
    print("=" * 60)
    sys.stdout.flush()

    # Monitor loop
    start_time = time.time()
    try:
        while True:
            time.sleep(3)
            # Check processes alive
            if p_geth.poll() is not None:
                print(f"ALERT: Geth exited with code {p_geth.returncode}")
                break
            if p_beacon.poll() is not None:
                print(f"ALERT: Beacon Node exited with code {p_beacon.returncode}")
                break
            if p_val.poll() is not None:
                print(f"ALERT: Validator exited with code {p_val.returncode}")
                break

            block_num = check_rpc()
            slot, prop = check_beacon()
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed:03d}s] Geth EL Block: {block_num} | Beacon CL Slot: {slot} (Proposer: {prop})")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nStopping devnet processes...")
    finally:
        for p in [p_val, p_beacon, p_geth]:
            if p and p.poll() is None:
                p.terminate()
        print("Devnet stopped.")

if __name__ == '__main__':
    main()
