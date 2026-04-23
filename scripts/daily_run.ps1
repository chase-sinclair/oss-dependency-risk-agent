# OSS Risk Agent — Daily Pipeline Run
$today = Get-Date -Format "yyyy-MM-dd"
Write-Host "Running pipeline for $today"

python scripts\run_ingestion.py --date $today
python scripts\run_silver.py --trigger --wait
python scripts\run_gold_models.py
python scripts\run_agent.py --limit 10
python scripts\run_indexer.py

Write-Host "Pipeline complete for $today"
