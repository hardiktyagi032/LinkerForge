param(
    [int]$WaitMinutes = 120
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$queueDir = Join-Path $repoRoot 'artifacts\transfer-training-queue-001'
New-Item -ItemType Directory -Path $queueDir -Force | Out-Null
$transcript = Join-Path $queueDir 'queue-transcript.log'
Start-Transcript -LiteralPath $transcript -Append | Out-Null
try {
    $focalManifestPath = Join-Path $repoRoot 'artifacts\esm2-35m-focal-gamma2-run-001\manifest.json'
    $deadline = (Get-Date).AddMinutes($WaitMinutes)
    while ($true) {
        if (-not (Test-Path -LiteralPath $focalManifestPath)) {
            throw 'Focal-loss run manifest is missing.'
        }
        $focalManifest = Get-Content -LiteralPath $focalManifestPath -Raw | ConvertFrom-Json
        if ($focalManifest.status -eq 'completed') { break }
        if ($focalManifest.status -eq 'failed') { throw 'Focal-loss run failed; queue stopped.' }
        if ((Get-Date) -ge $deadline) { throw 'Timed out waiting for focal-loss run.' }
        Start-Sleep -Seconds 30
    }
    Write-Host 'Focal-loss run complete. Starting three 8M screening trials.'
    & (Join-Path $PSScriptRoot 'run_transfer_loss_trials.ps1') -BackboneSize 8m
    if (-not $?) { throw '8M strategy screen failed.' }

    $python = Join-Path $repoRoot '.venv-gpu\Scripts\python.exe'
    $comparison = Join-Path $PSScriptRoot 'compare_detector_experiments.py'
    $baseline = Join-Path $repoRoot 'artifacts\esm2-linker-run-001'
    $trialDirs = @(
        (Join-Path $repoRoot 'artifacts\transfer-8m-asymmetric-run-001'),
        (Join-Path $repoRoot 'artifacts\transfer-8m-bce_tversky-run-001'),
        (Join-Path $repoRoot 'artifacts\transfer-8m-hard_negative-run-001')
    )
    $comparisonJson = & $python $comparison $baseline $trialDirs | Out-String
    if ($LASTEXITCODE -ne 0) { throw 'Validation comparison failed.' }
    $comparisonObject = $comparisonJson | ConvertFrom-Json
    $baselineScore = ($comparisonObject.runs | Where-Object { $_.directory -eq $baseline }).best_validation_auprc
    # The comparison code normalizes paths; normalize here as well.
    if ($null -eq $baselineScore) { $baselineScore = $comparisonObject.runs[0].best_validation_auprc }
    $eligible = @($comparisonObject.runs | Select-Object -Skip 1 | Where-Object {
        $_.best_validation_auprc -ge ($baselineScore + 0.01)
    } | Sort-Object best_validation_auprc -Descending)
    Write-Host "8M baseline AUPRC: $baselineScore"
    foreach ($run in $comparisonObject.runs) {
        Write-Host "$($run.loss.name): $($run.best_validation_auprc)"
    }
    if ($eligible.Count -eq 0) {
        Write-Host 'No 8M strategy cleared +0.01 AUPRC; no 35M confirmation queued.'
        return
    }
    $winner = $eligible[0]
    $lossName = $winner.loss.name
    $gamma = if ($lossName -eq 'asymmetric') { '2' } else { '0' }
    $out = Join-Path $repoRoot "artifacts\transfer-35m-$lossName-run-001"
    if (Test-Path -LiteralPath $out) {
        throw "35M destination already exists; refusing overwrite: $out"
    }
    $env:HF_HOME = Join-Path $repoRoot 'artifacts\hf-cache'
    $env:HF_HUB_OFFLINE = '1'
    Write-Host "Confirming 8M winner on 35M: $lossName"
    Push-Location $repoRoot
    try {
        & $python (Join-Path $PSScriptRoot 'train_esm2_linker_detector.py') --train (Join-Path $repoRoot 'data\processed\dld_reference\dld_train.jsonl.gz') --validation (Join-Path $repoRoot 'data\processed\dld_reference\dld_validation.jsonl.gz') --output-dir $out --model-id facebook/esm2_t12_35M_UR50D --revision 6fbf070e65b0b7291e7bbcd451118c216cff79d8 --epochs 10 --batch-size 4 --positive-weight 6 --focal-gamma $gamma --loss-name $lossName
        if ($LASTEXITCODE -ne 0) { throw '35M confirmation training failed.' }
    } finally {
        Pop-Location
    }
    Write-Host 'Transfer training queue completed. Blind fold was not opened.'
} finally {
    Stop-Transcript | Out-Null
}
