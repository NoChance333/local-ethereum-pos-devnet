import urllib.request
import concurrent.futures
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_file_info(url):
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = opener.open(req)
    final_url = resp.geturl()
    content_length = int(resp.headers.get('Content-Length', 0))
    return final_url, content_length

def download_chunk(url, start, end, out_path, chunk_idx):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Range': f'bytes={start}-{end}'
    })
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                expected = end - start + 1
                if len(data) != expected:
                    raise IOError(f"Expected {expected} bytes, got {len(data)}")
                with open(out_path, 'r+b') as f:
                    f.seek(start)
                    f.write(data)
                return True
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Chunk {chunk_idx} failed after {max_retries} attempts: {e}")
                raise
            time.sleep(1 + attempt)

def parallel_download(url, target_path, num_workers=16):
    print(f"Resolving {url}...")
    final_url, total_bytes = get_file_info(url)
    print(f"Downloading {os.path.basename(target_path)} ({total_bytes / (1024*1024):.2f} MB) using {num_workers} threads...")

    part_path = target_path + ".part"
    with open(part_path, 'wb') as f:
        f.seek(total_bytes - 1)
        f.write(b'\0')

    chunk_size = 2 * 1024 * 1024 # 2MB
    chunks = []
    chunk_idx = 0
    for start in range(0, total_bytes, chunk_size):
        end = min(start + chunk_size - 1, total_bytes - 1)
        chunks.append((final_url, start, end, part_path, chunk_idx))
        chunk_idx += 1

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(download_chunk, *c) for c in chunks]
        done_count = 0
        for f in concurrent.futures.as_completed(futures):
            f.result()
            done_count += 1
            if done_count % 10 == 0 or done_count == len(chunks):
                mb = (done_count * chunk_size) / (1024 * 1024)
                elapsed = time.time() - t0
                speed = mb / elapsed if elapsed > 0 else 0
                print(f"[{os.path.basename(target_path)}] {done_count}/{len(chunks)} chunks ({speed:.2f} MB/s)")

    if os.path.exists(target_path):
        os.remove(target_path)
    os.rename(part_path, target_path)
    print(f"Completed {os.path.basename(target_path)} in {time.time() - t0:.2f}s")

if __name__ == '__main__':
    downloads = [
        ("https://github.com/OffchainLabs/prysm/releases/download/v7.1.8/prysmctl-v7.1.8-windows-amd64.exe", os.path.join(BASE_DIR, "prysmctl.exe")),
        ("https://github.com/OffchainLabs/prysm/releases/download/v7.1.8/beacon-chain-v7.1.8-windows-amd64.exe", os.path.join(BASE_DIR, "beacon-chain.exe")),
        ("https://github.com/OffchainLabs/prysm/releases/download/v7.1.8/validator-v7.1.8-windows-amd64.exe", os.path.join(BASE_DIR, "validator.exe")),
    ]
    for url, target in downloads:
        if os.path.exists(target) and os.path.getsize(target) > 10 * 1024 * 1024:
            print(f"{os.path.basename(target)} already exists, skipping.")
            continue
        parallel_download(url, target, num_workers=24)
