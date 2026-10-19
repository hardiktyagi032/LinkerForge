param([string]$OutDir = "literature")

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$queries = @(
  'protein interdomain linker prediction',
  'protein domain boundary prediction linker',
  'natural protein linker identification',
  'fusion protein peptide linker design',
  'synthetic fusion protein linker optimization',
  'protein linker sequence machine learning',
  'protein linker generative design',
  'protein domain insertion site prediction',
  'circular permutation linker design',
  'protein fusion site selection',
  'protein loop design domain connection',
  'multidomain protein linker structure dynamics',
  'protein fusion structural modeling linker',
  'peptide linker sequence function fusion protein'
)
$records = @{}
$queryLog = @()
foreach ($query in $queries) {
  $encoded = [uri]::EscapeDataString($query)
  $url = "https://api.openalex.org/works?search=$encoded&per-page=200&filter=type:article&select=id,doi,title,publication_year,primary_location,authorships&mailto=linkerforge-literature@example.org"
  $response = Invoke-RestMethod -Uri $url -TimeoutSec 90
  $added = 0
  foreach ($work in $response.results) {
    if (-not $work.id -or -not $work.title) { continue }
    if (-not $records.ContainsKey($work.id)) {
      $journal = if ($work.primary_location -and $work.primary_location.source) { $work.primary_location.source.display_name } else { $null }
      $authors = @($work.authorships | Select-Object -First 4 | ForEach-Object { $_.author.display_name }) -join '; '
      $records[$work.id] = [pscustomobject]@{
        openalex_id = $work.id
        doi = $work.doi
        title = $work.title
        year = $work.publication_year
        journal = $journal
        authors_first_four = $authors
        matched_queries = @($query)
        screening_status = 'retrieved_not_screened'
      }
      $added++
    } else {
      $records[$work.id].matched_queries = @($records[$work.id].matched_queries) + $query
    }
  }
  $queryLog += [pscustomobject]@{ query=$query; api_total=$response.meta.count; returned=@($response.results).Count; new_unique=$added }
  Write-Output "$query : $added new; $($records.Count) total"
  Start-Sleep -Milliseconds 500
}
$ordered = @($records.Values | Sort-Object title)
$ordered | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -Path (Join-Path $OutDir 'openalex_screening_pool.json')
$ordered | Select-Object openalex_id,doi,title,year,journal,authors_first_four,@{n='matched_queries';e={$_.matched_queries -join ' | '}},screening_status | Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutDir 'openalex_screening_pool.csv')
$queryLog | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 -Path (Join-Path $OutDir 'search_log.json')
Write-Output "FINAL_UNIQUE=$($ordered.Count)"
