# PowerShell script to copy and run TypeE fixed scripts in batches
$WORKDIR = "C:\Users\user\projects\meep-kb"
$WORKER = "meep-pilot-worker"
$PYTHON = "/opt/conda/envs/mp/bin/python3"
$TIMEOUT = 120

$IDS = @(336,339,340,342,349,352,358,362,368,386,388,395,397,399,403,411,507,510,511,514,522,525,533,537,544,570,572,579,581,583,588,599,601)

$results = @{success=@(); failed=@(); timeout=@()}
$log_path = "$WORKDIR\typee_run_log.txt"

"TypeE Run Log - $(Get-Date)" | Out-File $log_path -Encoding utf8

# Process in batches of 4
$batch_size = 4
for ($i = 0; $i -lt $IDS.Count; $i += $batch_size) {
    $batch = $IDS[$i..([Math]::Min($i + $batch_size - 1, $IDS.Count - 1))]
    "--- Batch: $batch ---" | Out-File $log_path -Append -Encoding utf8
    Write-Host "=== Running batch: $batch ==="
    
    $jobs = @()
    foreach ($id in $batch) {
        $src = "$WORKDIR\typee_fixed_$id.py"
        $dst_container = "/tmp/typee_$id.py"
        
        # Copy to worker
        docker cp $src "${WORKER}:${dst_container}" 2>&1
        
        # Start background job
        $job = Start-Job -ScriptBlock {
            param($id, $worker, $python, $timeout)
            $result = docker exec --timeout $timeout $worker $python /tmp/typee_$id.py 2>&1
            $exit_code = $LASTEXITCODE
            [PSCustomObject]@{
                id = $id
                exit_code = $exit_code
                output = ($result -join "`n")
            }
        } -ArgumentList $id, $WORKER, $PYTHON, $TIMEOUT
        
        $jobs += @{id=$id; job=$job}
        Write-Host "  Started job for ID $id"
    }
    
    # Wait for all jobs in this batch
    Write-Host "  Waiting for batch to complete (max $TIMEOUT s)..."
    foreach ($item in $jobs) {
        $id = $item.id
        $job = $item.job
        $res = Receive-Job -Job $job -Wait -Timeout ($TIMEOUT + 10)
        Remove-Job -Job $job -Force
        
        if ($res) {
            $ec = $res.exit_code
            $out = $res.output
            $preview = $out.Substring(0, [Math]::Min(200, $out.Length))
            "ID $id exit_code=$ec | $preview" | Out-File $log_path -Append -Encoding utf8
            
            if ($ec -eq 0) {
                Write-Host "  [OK] ID $id"
                $results.success += $id
            } else {
                Write-Host "  [FAIL] ID $id (exit=$ec)"
                $results.failed += $id
                "FULL OUTPUT ID $id:" | Out-File $log_path -Append -Encoding utf8
                $out | Out-File $log_path -Append -Encoding utf8
            }
        } else {
            Write-Host "  [TIMEOUT] ID $id"
            $results.timeout += $id
            "TIMEOUT ID $id" | Out-File $log_path -Append -Encoding utf8
        }
    }
    
    Write-Host "  Batch done. Success so far: $($results.success.Count)"
    Start-Sleep -Seconds 2
}

Write-Host "`n=== SUMMARY ==="
Write-Host "Success: $($results.success)"
Write-Host "Failed: $($results.failed)"
Write-Host "Timeout: $($results.timeout)"

# Save results
$results | ConvertTo-Json -Depth 3 | Out-File "$WORKDIR\typee_run_results.json" -Encoding utf8
