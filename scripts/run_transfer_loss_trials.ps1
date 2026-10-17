param(
    [ValidateSet('8m', '35m')]
    [string]$BackboneSize = '8m'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv-gpu\Scripts\python.exe'
$trainer = Join-Path $PSScriptRoot 'train_esm2_linker_detector.py'
$train = Join-Path $repoRoot 'data\processed\dld_reference\dld_train.jsonl.gz'
$validation = Join-Path $repoRoot 'data\processed\dld_reference\dld_validation.jsonl.gz'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $train) -or -not (Test-Path -LiteralPath $validation)) {
    throw 'The pinned local Python environment or DLD reference shards are missing.'
}
$env:HF_HOME = Join-Path $repoRoot 'artifacts\hf-cache'
$env:HF_HUB_OFFLINE = '1'
if ($BackboneSize -eq '8m') {
    $modelId = 'facebook/esm2_t6_8M_UR50D'
    $revision = 'c731040fcd8d73dceaa04b0a8e6329b345b0f5df'
} else {
    $modelId = 'facebook/esm2_t12_35M_UR50D'
    $revision = '6fbf070e65b0b7291e7bbcd451118c216cff79d8'
}
$trials = @(
    @{ name = 'asymmetric'; gamma = '2' },
    @{ name = 'bce_tversky'; gamma = '0' },
    @{ name = 'hard_negative'; gamma = '0' }
)
Push-Location $repoRoot
try {
    foreach ($trial in $trials) {
        $out = Join-Path $repoRoot ("artifacts\transfer-$BackboneSize-$($trial.name)-run-001")
        if (Test-Path -LiteralPath $out) {
            $manifestPath = Join-Path $out 'manifest.json'
            if (-not (Test-Path -LiteralPath $manifestPath)) {
                throw "Existing trial directory has no manifest: $out"
            }
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
            if ($manifest.status -eq 'completed') {
                Write-Host "Already completed: $out"
                continue
            }
            if ($manifest.model_id -ne $modelId -or $manifest.revision -ne $revision -or
                $manifest.loss.name -ne $trial.name -or
                [double]$manifest.loss.focal_gamma -ne [double]$trial.gamma) {
                throw "Incomplete trial has mismatched configuration: $out"
            }
            $resume = Join-Path $out 'latest.pt'
            if (-not (Test-Path -LiteralPath $resume)) {
                throw "Incomplete trial has no checkpoint: $out"
            }
            Write-Host "Resuming $($trial.name) from $resume"
        } else {
            $resume = $null
        }
        Write-Host "Starting $($trial.name) on $BackboneSize"
        $arguments = @($trainer,'--train',$train,'--validation',$validation,
                       '--output-dir',$out,'--model-id',$modelId,'--revision',$revision,
                       '--epochs','10','--batch-size','4','--positive-weight','6',
                       '--focal-gamma',$trial.gamma,'--loss-name',$trial.name)
        if ($resume) { $arguments += @('--resume',$resume) }
        & $python @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Training failed for $($trial.name) with exit code $LASTEXITCODE"
        }
    }
} finally {
    Pop-Location
}
