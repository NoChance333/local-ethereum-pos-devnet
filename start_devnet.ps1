$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($ScriptDir)) { $ScriptDir = Get-Location }

# Stop existing processes if any
Get-Process geth, beacon-chain, validator -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

$LogsDir = Join-Path $ScriptDir "logs"
if (!(Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }

$jwtFile = Join-Path $ScriptDir "jwt.hex"
if (!(Test-Path $jwtFile)) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $hex = [System.BitConverter]::ToString($bytes) -replace '-'
    $hex.ToLower() | Out-File -FilePath $jwtFile -NoNewline -Encoding ascii
    Write-Host "Generated new jwt.hex"
}

# Start Geth
$gethExe = Join-Path $ScriptDir "geth.exe"
$gethData = Join-Path $ScriptDir "geth-data"
if (!(Test-Path $gethData)) {
    Write-Host "Initializing Geth datadir from genesis.json..."
    & $gethExe --datadir $gethData init (Join-Path $ScriptDir "genesis.json")
}
$gethArgs = @(
    "--datadir", $gethData,
    "--networkid", "12345",
    "--http",
    "--http.api", "eth,net,web3,personal,engine",
    "--http.port", "8545",
    "--http.addr", "127.0.0.1",
    "--http.corsdomain", "*",
    "--authrpc.port", "8551",
    "--authrpc.jwtsecret", $jwtFile,
    "--authrpc.addr", "127.0.0.1",
    "--authrpc.vhosts", "*",
    "--nodiscover",
    "--syncmode", "full"
)
$gethProc = Start-Process -FilePath $gethExe -ArgumentList $gethArgs -RedirectStandardOutput (Join-Path $LogsDir "geth.log") -RedirectStandardError (Join-Path $LogsDir "geth_err.log") -PassThru
Write-Host "Started Geth (PID: $($gethProc.Id))"
Start-Sleep -Seconds 2

# Start Beacon Chain
$beaconExe = Join-Path $ScriptDir "beacon-chain.exe"
$beaconData = Join-Path $ScriptDir "beacon-data"
$genesisSsz = Join-Path $ScriptDir "genesis.ssz"
$configYaml = Join-Path $ScriptDir "config.yaml"
$beaconArgs = @(
    "--datadir", $beaconData,
    "--genesis-state", $genesisSsz,
    "--chain-config-file", $configYaml,
    "--execution-endpoint", "http://127.0.0.1:8551",
    "--jwt-secret", $jwtFile,
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
)
$beaconProc = Start-Process -FilePath $beaconExe -ArgumentList $beaconArgs -RedirectStandardOutput (Join-Path $LogsDir "beacon.log") -RedirectStandardError (Join-Path $LogsDir "beacon_err.log") -PassThru
Write-Host "Started Beacon Node (PID: $($beaconProc.Id))"
Start-Sleep -Seconds 2

# Start Validator Client
$valExe = Join-Path $ScriptDir "validator.exe"
$valData = Join-Path $ScriptDir "validator-data"
$walletDir = Join-Path $ScriptDir "validator-wallet"
$pwdFile = Join-Path $ScriptDir "wallet_pass.txt"
$valArgs = @(
    "--datadir", $valData,
    "--wallet-dir", $walletDir,
    "--wallet-password-file", $pwdFile,
    "--beacon-rpc-provider", "127.0.0.1:4000",
    "--chain-config-file", $configYaml,
    "--accept-terms-of-use",
    "--suggested-fee-recipient", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
)
$valProc = Start-Process -FilePath $valExe -ArgumentList $valArgs -RedirectStandardOutput (Join-Path $LogsDir "validator.log") -RedirectStandardError (Join-Path $LogsDir "validator_err.log") -PassThru
Write-Host "Started Validator Client (PID: $($valProc.Id))"

@{
    GethPid = $gethProc.Id
    BeaconPid = $beaconProc.Id
    ValidatorPid = $valProc.Id
} | ConvertTo-Json | Set-Content (Join-Path $ScriptDir "pids.json")

Write-Host "All nodes launched successfully in background."
