Get-Process geth, beacon-chain, validator -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "Stopped all running Geth, Beacon-Chain, and Validator processes."
