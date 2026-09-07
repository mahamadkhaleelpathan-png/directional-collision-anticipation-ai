$body = @{sources = @('nexar')} | ConvertTo-Json
Write-Host "Request body: $body"
$response = Invoke-WebRequest -Uri 'http://localhost:8000/api/dataset/download' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 30
Write-Host "Status: $($response.StatusCode)"
Write-Host "Content: $($response.Content)"