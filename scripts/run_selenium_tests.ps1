<#
.SYNOPSIS
    Ejecuta la suite de pruebas E2E automatizadas en Google Chrome con Selenium.

.PARAMETER Headless
    Ejecuta Google Chrome en modo headless (sin ventana visible). Por defecto abre Chrome visible.

.PARAMETER BaseUrl
    URL base del API Gateway / Frontend (por defecto http://localhost:8000).
#>
param(
    [switch]$Headless,
    [string]$BaseUrl = "http://localhost:8000"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Ejecutando Pruebas E2E con Selenium (Google Chrome)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$env:APP_BASE_URL = $BaseUrl
if ($Headless) {
    $env:SELENIUM_HEADLESS = "1"
    Write-Host "Modo: Headless (sin interfaz gráfica)" -ForegroundColor Yellow
} else {
    $env:SELENIUM_HEADLESS = "0"
    Write-Host "Modo: Chrome Visible (demostración paso a paso)" -ForegroundColor Green
}
Write-Host "URL objetivo: $env:APP_BASE_URL" -ForegroundColor Gray

python -m pytest tests/selenium -m selenium -v -s
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`nSuite Selenium finalizada correctamente." -ForegroundColor Green
} else {
    Write-Host "`nLa suite Selenium terminó con errores (exit code: $exitCode)." -ForegroundColor Red
}

exit $exitCode
