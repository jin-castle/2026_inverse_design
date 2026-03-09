# Run TypeC simulations 2 at a time, 16 MPI cores each, 600s timeout
$IDS = @(333,341,353,375,378,381,389,400,505,513,526,528,539,548,554,559,562,573,575,592)
$TIMEOUT = 600
$PROJ = "C:\Users\user\projects\meep-kb"

$results = @{ successful = @(); timeout = @(); errors = @() }

# Process in batches of 2
for ($i = 0; $i -lt $IDS.Count; $i += 2) {
    $batch = $IDS[$i..([Math]::Min($i+1, $IDS.Count-1))]
    Write-Host "`n=== BATCH: $($batch -join ', ') ===" -ForegroundColor Cyan
    
    # Start both in parallel
    $jobs = @()
    foreach ($eid in $batch) {
        $src = "$PROJ\typec_fixed_$eid.py"
        if (!(Test-Path $src)) {
            Write-Host "ERROR: $src not found, skipping $eid" -ForegroundColor Red
            $results.errors += @{ id = $eid; reason = "source file not found" }
            continue
        }
        
        # docker cp
        $cp_out = docker cp $src "meep-pilot-worker:/tmp/typec_$eid.py" 2>&1
        Write-Host "cp $eid -> $cp_out"
        
        # Start simulation in background (detached)
        $cmd = "/usr/bin/mpirun --allow-run-as-root -np 16 /opt/conda/envs/mp/bin/python3 /tmp/typec_$eid.py > /tmp/typec_$eid.log 2>&1"
        docker exec -d meep-pilot-worker bash -c $cmd
        Write-Host "Started simulation $eid" -ForegroundColor Green
        $jobs += $eid
    }
    
    if ($jobs.Count -eq 0) { continue }
    
    # Wait 600 seconds
    Write-Host "Waiting 600s for batch [$($jobs -join ', ')]..." -ForegroundColor Yellow
    Start-Sleep -Seconds $TIMEOUT
    
    # Check results for each in batch
    foreach ($eid in $jobs) {
        Write-Host "`n--- Checking $eid ---"
        
        # Check if process is still running
        $running = docker exec meep-pilot-worker bash -c "pgrep -f 'typec_$eid' 2>/dev/null | head -1" 2>&1
        if ($running -match '\d+') {
            Write-Host "TIMEOUT: $eid still running, killing..." -ForegroundColor Red
            docker exec meep-pilot-worker bash -c "pkill -f 'typec_$eid' 2>/dev/null; true"
            $results.timeout += $eid
            continue
        }
        
        # Get log tail
        $log = docker exec meep-pilot-worker bash -c "tail -20 /tmp/typec_$eid.log 2>&1" 2>&1
        Write-Host "Log tail: $log"
        
        # Check for images
        $imgs = docker exec meep-pilot-worker bash -c "ls /tmp/kb_results/typec_${eid}_*.png 2>/dev/null" 2>&1
        if ($imgs -match "\.png") {
            Write-Host "SUCCESS: $eid has images" -ForegroundColor Green
            $results.successful += $eid
        } else {
            # Check if log has error
            $errCheck = docker exec meep-pilot-worker bash -c "grep -i 'error\|exception\|traceback' /tmp/typec_$eid.log 2>/dev/null | tail -5" 2>&1
            if ($errCheck) {
                Write-Host "ERROR: $eid failed with: $errCheck" -ForegroundColor Red
                $results.errors += @{ id = $eid; reason = $errCheck.Substring(0, [Math]::Min($errCheck.Length, 200)) }
            } else {
                # Completed but no images (script may not produce images)
                Write-Host "COMPLETED (no images): $eid" -ForegroundColor Yellow
                $results.successful += $eid
            }
        }
    }
}

# Save results
$results | ConvertTo-Json -Depth 5 | Set-Content "$PROJ\agent2b_results.json" -Encoding UTF8
Write-Host "`n=== DONE ===" -ForegroundColor Cyan
Write-Host "Successful: $($results.successful.Count)"
Write-Host "Timeout: $($results.timeout.Count)"
Write-Host "Errors: $($results.errors.Count)"
