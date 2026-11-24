[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $PSScriptRoot '../.tools/bin')
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$target = [IO.Path]::GetFullPath($Destination)
[IO.Directory]::CreateDirectory($target) | Out-Null
$scratch = Join-Path ([IO.Path]::GetTempPath()) ("vllm-ops-tools-" + [guid]::NewGuid())
[IO.Directory]::CreateDirectory($scratch) | Out-Null

function Install-Tool($Url, $Archive, $Checksum, $Member, $Output) {
    $download = Join-Path $scratch $Archive
    $checksumFile = Join-Path $scratch "$Archive.sum"
    Invoke-WebRequest -Uri $Checksum -OutFile $checksumFile
    $checksums = Get-Content -Raw -LiteralPath $checksumFile
    $name = [regex]::Escape($Archive)
    $line = [regex]::Match($checksums, "(?im)^([a-f0-9]{64})(?:\s+\*?$name)?\s*$")
    if (-not $line.Success) { throw "No SHA-256 for $Archive." }
    Invoke-WebRequest -Uri $Url -OutFile $download
    if ((Get-FileHash -LiteralPath $download).Hash -ne $line.Groups[1].Value) {
        throw "SHA-256 mismatch for $Archive."
    }
    if ($Member) {
        Expand-Archive -LiteralPath $download -DestinationPath $scratch -Force
        $download = Join-Path $scratch $Member
    }
    Copy-Item -LiteralPath $download -Destination (Join-Path $target $Output) -Force
    Write-Host "Installed $Output"
}

try {
    $kind = 'https://github.com/kubernetes-sigs/kind/releases/download/v0.30.0/kind-windows-amd64'
    $kubectl = 'https://dl.k8s.io/release/v1.34.1/bin/windows/amd64/kubectl.exe'
    $helm = 'https://get.helm.sh/helm-v3.19.0-windows-amd64.zip'
    $k6 = 'https://github.com/grafana/k6/releases/download/v1.3.0'
    Install-Tool $kind 'kind-windows-amd64' "$kind.sha256sum" '' 'kind.exe'
    Install-Tool $kubectl 'kubectl.exe' "$kubectl.sha256" '' 'kubectl.exe'
    Install-Tool $helm 'helm-v3.19.0-windows-amd64.zip' "$helm.sha256sum" 'windows-amd64/helm.exe' 'helm.exe'
    Install-Tool "$k6/k6-v1.3.0-windows-amd64.zip" 'k6-v1.3.0-windows-amd64.zip' "$k6/k6-v1.3.0-checksums.txt" 'k6-v1.3.0-windows-amd64/k6.exe' 'k6.exe'
    Write-Host "Tool directory $target"
} finally {
    $resolved = [IO.Path]::GetFullPath($scratch)
    $prefix = [IO.Path]::Combine([IO.Path]::GetTempPath(), 'vllm-ops-tools-')
    if ($resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
