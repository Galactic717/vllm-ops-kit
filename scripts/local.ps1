[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$Port = 9941,
    [string]$LlamaHome = (Join-Path $env:LOCALAPPDATA 'Programs/llama.cpp'),
    [string]$ModelPath,
    [string]$GatewayImage = 'verifine-slm:local',
    [string]$ReportPath
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$backend = "http://127.0.0.1:$Port"
$server = $null
$containerId = $null
$originalEnv = @{}
$started = [Diagnostics.Stopwatch]::StartNew()

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments)][string[]]$Arguments)
    $result = & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Docker command failed. Check Docker Desktop and the gateway image.' }
    return $result
}

function Wait-Healthy([string]$Url, [int]$Seconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        try {
            Invoke-RestMethod -Uri $Url -TimeoutSec 3 | Out-Null
            return
        } catch {
            if ($server -and $server.HasExited) { throw 'llama-server exited while loading the model.' }
            Start-Sleep -Milliseconds 350
        }
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Timed out waiting for $Url."
}

try {
    if ($ModelPath) {
        if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
            throw "Port $Port is already listening. Supply a separate port for a new model."
        }
        $modelFile = (Resolve-Path -LiteralPath $ModelPath).Path
        $executable = Join-Path $LlamaHome 'llama-server.exe'
        if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw "Missing $executable." }
        $logs = Join-Path ([System.IO.Path]::GetTempPath()) ("vllm-ops-" + [guid]::NewGuid())
        $processOptions = @{
            FilePath = $executable; WorkingDirectory = $LlamaHome; WindowStyle = 'Hidden'
            ArgumentList = ('--model "{0}" --alias ops-local --host 127.0.0.1 --port {1} --ctx-size 2048 --parallel 1 --gpu-layers 0 --metrics --offline' -f $modelFile, $Port)
            RedirectStandardOutput = "$logs.out.log"; RedirectStandardError = "$logs.err.log"
            PassThru = $true
        }
        $server = Start-Process @processOptions
        Write-Host "llama-server logs at $logs.err.log"
    }

    Wait-Healthy "$backend/health" 120
    $backendHeaders = @{}
    if ($env:LLAMA_API_KEY) { $backendHeaders.Authorization = "Bearer $env:LLAMA_API_KEY" }
    $models = Invoke-RestMethod -Uri "$backend/v1/models" -Headers $backendHeaders -TimeoutSec 10
    $model = $models.data[0].id
    if (-not $model) { throw 'llama.cpp did not report a model ID.' }

    $gatewayKey = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $containerEnv = @{
        VERIFINE_BACKEND = 'llama'
        VERIFINE_BACKEND_URL = "http://host.docker.internal:$Port/v1"
        VERIFINE_MODEL = $model
        VERIFINE_ALLOW_NETWORK_BACKEND = '1'
        VERIFINE_GATEWAY_KEY = $gatewayKey
        VERIFINE_API_KEY = $env:LLAMA_API_KEY
    }
    $envArgs = @()
    foreach ($name in $containerEnv.Keys) {
        $originalEnv[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $containerEnv[$name], 'Process')
        $envArgs += @('--env', $name)
    }
    $dockerArgs = @('run', '--detach', '--rm', '--user', '1000:1000', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp',
        '--memory', '384m', '--cpus', '1', '--publish', '127.0.0.1::8088')
    $containerId = Invoke-Docker @dockerArgs @envArgs $GatewayImage
    $published = Invoke-Docker 'port' $containerId '8088/tcp'
    $base = "http://$published"
    Wait-Healthy "$base/healthz" 30
    $headers = @{ Authorization = "Bearer $gatewayKey" }
    $served = Invoke-RestMethod -Uri "$base/v1/models" -Headers $headers -TimeoutSec 5
    if ($served.data[0].id -ne $model) { throw 'Gateway returned an unexpected model.' }

    $request = @{
        model = $model
        messages = @(@{role = 'user'; content = 'Reply with the word OK only. /no_think'})
        max_tokens = 160
        temperature = 0
    }
    $chatParams = @{
        Method = 'Post'; Uri = "$base/v1/chat/completions"; Headers = $headers
        ContentType = 'application/json'; Body = ($request | ConvertTo-Json -Depth 5); TimeoutSec = 180
    }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $answer = Invoke-RestMethod @chatParams
    $elapsed = [math]::Round($timer.Elapsed.TotalMilliseconds, 1)
    if (-not $answer.choices[0].message.content) { throw 'No assistant text returned through Verifine.' }
    $request.stream = $true
    $chatParams.Body = $request | ConvertTo-Json -Depth 5
    $stream = Invoke-WebRequest @chatParams -UseBasicParsing
    if ($stream.Content -notmatch 'data: \[DONE\]') { throw 'Streaming did not produce an SSE terminator.' }
    $gatewayMetrics = (Invoke-WebRequest -Uri "$base/metrics" -TimeoutSec 5 -UseBasicParsing).Content
    if ($gatewayMetrics -notmatch 'verifine_requests_total') { throw 'Gateway metrics are missing.' }
    $backendMetrics = $false
    try {
        $m = Invoke-WebRequest -Uri "$backend/metrics" -Headers $backendHeaders -TimeoutSec 3 -UseBasicParsing
        $backendMetrics = $m.StatusCode -eq 200
    } catch {
        Write-Host 'The active launcher does not expose llama.cpp metrics.'
    }

    $report = [ordered]@{
        time_utc = [DateTime]::UtcNow.ToString('o')
        model = $model
        model_file = if ($ModelPath) { Split-Path -Leaf $modelFile } else { $null }
        backend_port = $Port
        gateway = 'verifine-slm'
        chat_ms = $elapsed
        completion_tokens = $answer.usage.completion_tokens
        prompt_tokens = $answer.usage.prompt_tokens
        stream_done = $true
        gateway_metrics = $true
        llama_metrics = $backendMetrics
        wall_seconds = [math]::Round($started.Elapsed.TotalSeconds, 2)
    }
    $json = $report | ConvertTo-Json
    if ($ReportPath) {
        $output = [System.IO.Path]::GetFullPath($ReportPath)
        [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($output)) | Out-Null
        $json | Set-Content -LiteralPath $output -Encoding utf8
    }
    $json
} finally {
    if ($containerId) { & docker stop $containerId | Out-Null }
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id }
    foreach ($name in $originalEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $originalEnv[$name], 'Process')
    }
}
