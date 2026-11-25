# 大肥鱼本地栈健康检查（只读，纯文本）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File D:\大肥鱼\Tools\health.ps1

$ErrorActionPreference = 'SilentlyContinue'
"checkedAt: " + (Get-Date).ToString('o')

$mcp = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'MemoryService' -and $_.CommandLine -match 'mcp_server\.py' }
"memoryMcp: " + [bool]$mcp
if ($mcp) { "memoryMcpPid: " + @($mcp)[0].ProcessId }

try {
  $tags = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3
  "ollama: true"
  "embeddingModel: " + [bool]($tags.models | Where-Object { $_.name -like 'bge-m3*' })
} catch {
  "ollama: false"
  "embeddingModel: false"
}

$db = Join-Path $env:USERPROFILE '.dsh\memory-v2\memory.db'
"memoryDb: " + (Test-Path $db)
if (Test-Path $db) {
  "memoryDbMB: " + [math]::Round((Get-Item $db).Length / 1MB, 2)
  $py = @'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
def one(sql):
    return conn.execute(sql).fetchone()[0]
print("events=" + str(one("select count(*) from events")))
print("active=" + str(one("select count(*) from memories where status='active'")))
print("candidates=" + str(one("select count(*) from memories where status='candidate'")))
print("core=" + str(one("select count(*) from core_memories where status='confirmed'")))
conn.close()
'@
  $py | python - $db
}

$backupDir = 'D:\大肥鱼\Backups'
if (Test-Path $backupDir) {
  $latest = Get-ChildItem $backupDir -Filter *.zip | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($latest) {
    "lastBackup: " + $latest.Name
    "backupAgeHours: " + [math]::Round(((Get-Date) - $latest.LastWriteTime).TotalHours, 1)
  }
}
