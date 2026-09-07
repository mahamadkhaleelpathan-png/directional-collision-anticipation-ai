for ($i = 1; $i -le 60; $i++) {
    Start-Sleep -Seconds 10
    $output = curl.exe -s "http://localhost:8000/api/jobs/712bc4cd593a" 2>&1
    Write-Host ("Poll {0}: {1}" -f $i, $output)
    if ($output -like '*"status":"completed"*') {
        Write-Host "Job completed!"
        break
    }
    elseif ($output -like '*"status":"error"*') {
        Write-Host "Job failed!"
        break
    }
}