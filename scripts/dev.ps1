$ErrorActionPreference = "Stop"

python scripts/check.py
if ($LASTEXITCODE -ne 0) {
  Write-Host "[dev] Environment check failed. Fix errors above and retry."
  exit 1
}

$apiHost = if ($env:BENJAMIN_API_HOST) { $env:BENJAMIN_API_HOST } else { "127.0.0.1" }
$apiPort = if ($env:BENJAMIN_API_PORT) { $env:BENJAMIN_API_PORT } else { "8000" }
$apiBase = "http://$apiHost`:$apiPort"
$uiUrl = "$apiBase/ui"
$integrationsUrl = "$apiBase/integrations/status"
$provider = if ($env:BENJAMIN_LLM_PROVIDER) { $env:BENJAMIN_LLM_PROVIDER.ToLowerInvariant() } else { "off" }
$startVllm = if ($env:BENJAMIN_DEV_START_VLLM) { $env:BENJAMIN_DEV_START_VLLM.ToLowerInvariant() } else { "off" }
$stateDir = if ($env:BENJAMIN_STATE_DIR) { $env:BENJAMIN_STATE_DIR } else { Join-Path $HOME ".benjamin" }

Write-Host "[dev] state dir: $stateDir"
Write-Host "[dev] API base: $apiBase"
Write-Host "[dev] UI URL: $uiUrl"
Write-Host "[dev] Integrations status URL: $integrationsUrl"

$features = @("PLANNER", "SUMMARIZER", "DRAFTER", "RULE_BUILDER", "RETRIEVAL")
foreach ($feature in $features) {
  $name = "BENJAMIN_LLM_$feature"
  $value = [Environment]::GetEnvironmentVariable($name)
  if ([string]::IsNullOrWhiteSpace($value)) {
    $value = if ($provider -eq "off") { "off" } else { "on" }
  }
  Write-Host "[dev] feature $feature`: $value"
}

$children = New-Object System.Collections.Generic.List[System.Diagnostics.Process]

function Start-DevProcess {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string]$Arguments = ""
  )

  $proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru -NoNewWindow
  $script:children.Add($proc)
  Write-Host "[dev] started $Name (pid=$($proc.Id))"
}

if ($provider -eq "vllm" -and $startVllm -eq "on") {
  if ($env:BENJAMIN_DEV_VLLM_CMD) {
    $vllmUrl = if ($env:BENJAMIN_VLLM_URL) { $env:BENJAMIN_VLLM_URL } else { "http://127.0.0.1:8001/v1/chat/completions" }
    Write-Host "[dev] vLLM endpoint: $vllmUrl"
    Start-DevProcess -Name "vLLM" -FilePath "powershell" -Arguments "-NoProfile -Command $env:BENJAMIN_DEV_VLLM_CMD"
  }
  else {
    $model = if ($env:BENJAMIN_LLM_MODEL) { $env:BENJAMIN_LLM_MODEL } else { "zai-org/GLM-4.7" }
    Write-Host "[dev] BENJAMIN_DEV_START_VLLM=on but BENJAMIN_DEV_VLLM_CMD is not set; skipping vLLM startup."
    Write-Host "[dev] Example command: vllm serve '$model' --host 127.0.0.1 --port 8001 --dtype auto --max-model-len 8192 --gpu-memory-utilization 0.90"
  }
}
elseif ($provider -eq "vllm") {
  $vllmUrl = if ($env:BENJAMIN_VLLM_URL) { $env:BENJAMIN_VLLM_URL } else { "http://127.0.0.1:8001/v1/chat/completions" }
  Write-Host "[dev] vLLM endpoint: $vllmUrl (external)"
}

Start-DevProcess -Name "benjamin-api" -FilePath "benjamin-api"
Start-DevProcess -Name "benjamin-worker" -FilePath "benjamin-worker"

Write-Host "[dev] Running. Press Ctrl+C to stop."

try {
  while ($true) {
    Start-Sleep -Seconds 1
    foreach ($proc in @($children)) {
      if ($proc.HasExited) {
        throw "[dev] Process exited unexpectedly: pid=$($proc.Id) name=$($proc.ProcessName)"
      }
    }
  }
}
finally {
  Write-Host "[dev] stopping child processes..."
  foreach ($proc in @($children)) {
    try {
      if (-not $proc.HasExited) {
        Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue
      }
    }
    catch {
      Write-Host "[dev] warning: failed to stop pid=$($proc.Id): $($_.Exception.Message)"
    }
  }
}
