# 大肥鱼语音：启动 GPT-SoVITS API + 浏览器语音桥
# 幂等：端口已在监听就跳过；不重复起进程。
$ErrorActionPreference = 'Stop'

function Test-Port([int]$port) {
  return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-Port 9880)) {
  Write-Host 'starting GPT-SoVITS API on 9880...'
  Start-Process -FilePath 'D:\GPT-SoVITS\.venv\Scripts\python.exe' `
    -ArgumentList @('api_v2.py', '-a', '127.0.0.1', '-p', '9880') `
    -WorkingDirectory 'D:\GPT-SoVITS' -WindowStyle Hidden
} else {
  Write-Host 'GPT-SoVITS API already listening on 9880'
}

if (-not (Test-Port 9881)) {
  Write-Host 'starting voice bridge on 9881...'
  $python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
  if (-not $python) {
    $python = 'C:\Users\XHLENOVO\AppData\Local\Programs\Python\Python314\python.exe'
  }
  Start-Process -FilePath $python `
    -ArgumentList @('D:\大肥鱼\VoiceService\voice_bridge.py') `
    -WorkingDirectory 'D:\大肥鱼\VoiceService' -WindowStyle Hidden
} else {
  Write-Host 'voice bridge already listening on 9881'
}

Start-Sleep -Seconds 2
foreach ($port in 9880, 9881) {
  if (Test-Port $port) { Write-Host "OK 127.0.0.1:$port" }
  else { Write-Warning "NOT listening: $port" }
}
