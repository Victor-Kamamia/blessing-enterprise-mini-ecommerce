$hostAddress = "0.0.0.0"
$port = 8000

Write-Host "Starting Blessing Enterprise for phone preview..." -ForegroundColor Cyan
Write-Host "Phone URLs to try:" -ForegroundColor Yellow
Write-Host "  http://10.50.4.117:$port" -ForegroundColor Green
Write-Host "  http://192.168.137.1:$port  (use this if your phone is connected to your PC hotspot)" -ForegroundColor Green
Write-Host ""
python backend/server.py --host $hostAddress --port $port
