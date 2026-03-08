# start_ngrok.ps1 - ngrok 실행 / 확인 후 시작
$url  = "rubi-unmirrored-corruptibly.ngrok-free.dev"
$port = 8765

# 이미 터널이 살아있으면 스킵
$running = Get-Process ngrok -ErrorAction SilentlyContinue
if ($running) {
    try {
        $resp = Invoke-WebRequest "http://localhost:4040/api/tunnels" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        $json = $resp.Content | ConvertFrom-Json
        if ($json.tunnels.Count -gt 0) {
            Write-Host "ngrok already running: $($json.tunnels[0].public_url)"
            exit 0
        }
    } catch {}
    # 터널이 없으면 프로세스 종료 후 재시작
    Stop-Process -Name ngrok -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# ngrok 시작 (--url 플래그 사용, --domain deprecated)
Start-Process -FilePath "ngrok" `
    -ArgumentList @("http", $port, "--url=$url") `
    -WindowStyle Hidden

Start-Sleep -Seconds 3
Write-Host "ngrok started: https://$url"
