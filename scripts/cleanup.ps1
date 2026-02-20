param(
    [switch]$RemoveOutputFiles
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Cleaning Python caches and build artifacts..."

$dirsToRemove = @(
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "src/yahoo_screener_crawler.egg-info"
)

foreach ($dir in $dirsToRemove) {
    if (Test-Path $dir) {
        cmd /c rmdir /s /q "$dir" | Out-Null
    }
}

Get-ChildItem -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
    cmd /c rmdir /s /q "$($_.FullName)" | Out-Null
}

Get-ChildItem -Recurse -File -Include "*.pyc","*.pyo","*.pyd" | ForEach-Object {
    Remove-Item -Force $_.FullName
}

if (Test-Path "debug_after_apply.png") {
    Remove-Item -Force "debug_after_apply.png"
}

if (Test-Path "page.html") {
    Remove-Item -Force "page.html"
}

if ($RemoveOutputFiles -and (Test-Path "output")) {
    Write-Host "Removing files in output/..."
    Get-ChildItem "output" -File | ForEach-Object {
        Remove-Item -Force $_.FullName
    }
}

Write-Host "Cleanup done."
