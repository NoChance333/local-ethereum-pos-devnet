import os
import sys
import json
import uuid
import hashlib
import secrets
import re
import subprocess
from Crypto.Cipher import AES
from Crypto.Util import Counter
from py_ecc.bls import G2ProofOfPossession as bls

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def make_keystore_from_privkey(priv_hex, index, password):
    priv_bytes = bytes.fromhex(priv_hex)
    priv_int = int(priv_hex, 16)
    pub = bls.SkToPk(priv_int).hex()
    
    salt = secrets.token_bytes(32)
    iv = secrets.token_bytes(16)
    
    # KDF PBKDF2 with c=1 for fast devnet generation
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 1, 32)
    aes_key = dk[:16]
    
    # AES-128-CTR
    ctr = Counter.new(128, initial_value=int.from_bytes(iv, 'big'))
    cipher = AES.new(aes_key, AES.MODE_CTR, counter=ctr)
    ciphertext = cipher.encrypt(priv_bytes)
    
    # Checksum
    checksum = hashlib.sha256(dk[16:32] + ciphertext).hexdigest()
    
    keystore = {
        'crypto': {
            'kdf': {
                'function': 'pbkdf2',
                'params': {
                    'dklen': 32,
                    'c': 1,
                    'prf': 'hmac-sha256',
                    'salt': salt.hex()
                },
                'message': ''
            },
            'checksum': {
                'function': 'sha256',
                'params': {},
                'message': checksum
            },
            'cipher': {
                'function': 'aes-128-ctr',
                'params': {
                    'iv': iv.hex()
                },
                'message': ciphertext.hex()
            }
        },
        'description': f'interop validator key {index}',
        'pubkey': pub,
        'path': f'm/12381/3600/{index}/0/0',
        'uuid': str(uuid.uuid4()),
        'version': 4
    }
    return keystore

def main(num_validators=64, password="Password12345678"):
    keys_dir = os.path.join(BASE_DIR, "validator_keys")
    wallet_dir = os.path.join(BASE_DIR, "validator-wallet")
    pwd_file = os.path.join(BASE_DIR, "wallet_pass.txt")
    vector_file = os.path.join(BASE_DIR, "keygen_test_vector.yaml")
    validator_exe = os.path.join(BASE_DIR, "validator.exe")
    
    # Read private keys from vector file
    privs = []
    with open(vector_file, "r") as f:
        for line in f:
            m = re.search(r'privkey:\s*([0-9a-fA-F]+)', line)
            if m:
                privs.append(m.group(1))
            
    print(f"Loaded {len(privs)} keys from {vector_file}")
    
    os.makedirs(keys_dir, exist_ok=True)
    with open(pwd_file, "w") as f:
        f.write(password)
        
    print(f"Generating {num_validators} matching validator keystores in {keys_dir}...")
    for i in range(num_validators):
        ks = make_keystore_from_privkey(privs[i], i, password)
        with open(os.path.join(keys_dir, f"keystore-{i:03d}.json"), "w") as f:
            json.dump(ks, f, indent=2)
            
    print(f"Generated {num_validators} keystores successfully.")
    
    # Remove old wallet dir if exists
    if os.path.exists(wallet_dir):
        subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{wallet_dir}'"], capture_output=True)
        
    print(f"Importing keystores into Prysm wallet at {wallet_dir}...")
    cmd_import = [
        validator_exe,
        "accounts", "import",
        "--keys-dir", keys_dir,
        "--wallet-dir", wallet_dir,
        "--wallet-password-file", pwd_file,
        "--account-password-file", pwd_file,
        "--accept-terms-of-use"
    ]
    res = subprocess.run(cmd_import, capture_output=True, text=True)
    if res.returncode != 0:
        print("Import failed:", res.stderr)
        sys.exit(1)
    print("All 64 matching validator keys imported successfully into wallet!")

if __name__ == '__main__':
    main(64)
