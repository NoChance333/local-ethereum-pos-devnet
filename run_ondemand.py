import os
import sys
import time
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

def main():
    print("=" * 60)
    print("Starting On-Demand Local Ethereum Node (Geth standalone)...")
    print("Mode: 0 Auto-Blocks | Mine on Transaction Only | 100% Persistent")
    print(f"Working Directory: {BASE_DIR}")
    print("=" * 60)

    # 1. Stop any running processes
    stop_script = os.path.join(BASE_DIR, "stop_devnet.ps1")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", stop_script], capture_output=True)
    time.sleep(1)

    geth_exe = os.path.join(BASE_DIR, "geth.exe")
    if not os.path.exists(geth_exe):
        print(f"ERROR: geth.exe not found at {geth_exe}!")
        sys.exit(1)

    geth_data = os.path.join(BASE_DIR, "geth-data")
    genesis_file = os.path.join(BASE_DIR, "genesis.json")
    logs_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    reset_mode = "--reset" in sys.argv
    if reset_mode and os.path.exists(geth_data):
        print("Reset flag detected. Cleaning database for fresh start...")
        subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{geth_data}'"], capture_output=True)

    if not os.path.exists(geth_data):
        print("Initializing Geth with custom genesis...")
        res = subprocess.run([geth_exe, "--datadir", geth_data, "init", genesis_file], capture_output=True, text=True)
        if res.returncode != 0:
            print("Geth init failed:\n", res.stderr)
            sys.exit(1)
    else:
        print("Existing database found! Preserving previous state and deployed contracts.")
        print("Tip: Use 'python run_ondemand.py --reset' if you ever want to wipe and start from block 0.")

    f_geth = open(os.path.join(logs_dir, "geth.log"), "w")

    cmd_geth = [
        geth_exe,
        "--datadir", geth_data,
        "--dev",
        "--dev.period", "0",
        "--networkid", "12345",
        "--http",
        "--http.api", "eth,net,web3,personal,engine",
        "--http.port", "8545",
        "--http.addr", "127.0.0.1",
        "--http.corsdomain", "*"
    ]

    p_geth = subprocess.Popen(cmd_geth, stdout=f_geth, stderr=subprocess.STDOUT)
    time.sleep(2)

    init_block = check_rpc()
    print("=" * 60)
    print(f"On-Demand Node Running! PID: {p_geth.pid}")
    print("RPC Endpoint: http://127.0.0.1:8545 (Chain ID: 12345)")
    print(f"Current Block: {init_block}")
    print("Note: Blocks are sealed INSTANTLY when transactions arrive.")
    print("      No empty blocks are auto-mined while idle.")
    print("Press Ctrl+C to stop.")
    print("=" * 60)
    sys.stdout.flush()

    last_block = init_block
    try:
        while True:
            time.sleep(2)
            if p_geth.poll() is not None:
                print(f"ALERT: Geth exited with code {p_geth.returncode}")
                break
            cur = check_rpc()
            if cur is not None and cur != last_block:
                print(f"[*] NEW BLOCK SEALED! Block #{cur} (via transaction)")
                sys.stdout.flush()
                last_block = cur
    except KeyboardInterrupt:
        print("\nStopping Geth node...")
    finally:
        if p_geth.poll() is None:
            p_geth.terminate()
        print("Node stopped.")

if __name__ == '__main__':
    main()
