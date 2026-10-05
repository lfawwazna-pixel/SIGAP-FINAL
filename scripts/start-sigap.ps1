$ErrorActionPreference = 'Stop'
$sigapProject = Split-Path -Parent $PSScriptRoot
$sigapPython = Join-Path $sigapProject '.venv\Scripts\python.exe'
$sigapVision = Join-Path $sigapProject 'work\vision-env\Scripts\python.exe'
$sigapModel = Join-Path $sigapProject 'models\sigap_yolo26s\best.pt'
$sigapVite = Join-Path $sigapProject 'frontend\node_modules\vite\bin\vite.js'
$sigapLogs = Join-Path $sigapProject 'work\runtime'
foreach ($sigapFile in @($sigapPython,$sigapVision,$sigapModel,$sigapVite,(Join-Path $sigapProject 'frontend\dist\index.html'))) {
    if (!(Test-Path -LiteralPath $sigapFile)) { throw "File belum tersedia: $sigapFile. Ikuti docs/stage6-tracking.md dan build frontend." }
}
foreach ($sigapPort in @(18000,18001,15173)) {
    $sigapProbe = [Net.Sockets.TcpClient]::new()
    try { $sigapProbe.Connect('127.0.0.1',$sigapPort); throw "Port $sigapPort masih dipakai. Tutup proses SIGAP sebelumnya dahulu." }
    catch [Net.Sockets.SocketException] { }
    finally { $sigapProbe.Dispose() }
}
New-Item -ItemType Directory -Path $sigapLogs -Force | Out-Null
$env:SIGAP_YOLO_ENABLED = 'true'
$env:SIGAP_ADAPTIVE_VIDEO = 'true'
$env:SIGAP_ADAPTIVE_SYNTHETIC = 'false'
$env:ATCS_ENABLE_TEST_SOURCE = 'false'
$env:SIGAP_VISION_PYTHON = $sigapVision
$env:SIGAP_YOLO_MODEL = $sigapModel
$env:SIGAP_MEDIA_DIR = Join-Path $sigapProject 'work\media'
$env:SIGAP_ATCS_BASE_URL = 'http://127.0.0.1:18001'
$env:SIGAP_ALLOWED_ORIGINS = '["http://127.0.0.1:15173","http://localhost:15173"]'
$env:BACKEND_PROXY_TARGET = 'http://127.0.0.1:18000'
$sigapAtcs = Start-Process -FilePath $sigapPython -ArgumentList @('-m','uvicorn','atcs_simulator.app.main:app','--host','127.0.0.1','--port','18001','--workers','1') -WorkingDirectory $sigapProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $sigapLogs 'atcs.stdout.log') -RedirectStandardError (Join-Path $sigapLogs 'atcs.stderr.log') -PassThru
$sigapBackend = Start-Process -FilePath $sigapPython -ArgumentList @('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','18000','--workers','1') -WorkingDirectory $sigapProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $sigapLogs 'backend.stdout.log') -RedirectStandardError (Join-Path $sigapLogs 'backend.stderr.log') -PassThru
$sigapNode = (Get-Command node).Source
$sigapFrontend = Start-Process -FilePath $sigapNode -ArgumentList @(('"'+$sigapVite+'"'),'preview','--host','127.0.0.1','--port','15173','--configLoader','native') -WorkingDirectory (Join-Path $sigapProject 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $sigapLogs 'frontend.stdout.log') -RedirectStandardError (Join-Path $sigapLogs 'frontend.stderr.log') -PassThru
@{project=$sigapProject;atcs=$sigapAtcs.Id;backend=$sigapBackend.Id;frontend=$sigapFrontend.Id;
  started=@{atcs=$sigapAtcs.StartTime.ToUniversalTime().ToString('o');backend=$sigapBackend.StartTime.ToUniversalTime().ToString('o');frontend=$sigapFrontend.StartTime.ToUniversalTime().ToString('o')}} |
    ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $sigapLogs 'sigap-pids.json')
Write-Output 'SIGAP: http://127.0.0.1:15173/login'
