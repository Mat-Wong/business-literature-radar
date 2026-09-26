param(
    [ValidatePattern('^[0-9A-Za-z][0-9A-Za-z._-]*$')]
    [string]$Version = '0.1.0'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$distDir = Join-Path $projectRoot 'dist'
$buildDir = Join-Path $projectRoot 'build'
$exePath = Join-Path $distDir 'BusinessLiteratureRadar.exe'
$zipPath = Join-Path $distDir "business-literature-radar-v$Version-windows.zip"

foreach ($required in @('app.py', 'agent_bridge.py', 'app_settings.py', 'search_papers.py', 'search_v2.py', 'web', '.agents', '.claude')) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $required))) {
        throw "Missing release input: $required"
    }
}

$sourceFiles = @('app.py', 'agent_bridge.py', 'app_settings.py', 'search_papers.py', 'search_v2.py') |
    ForEach-Object { Join-Path $projectRoot $_ }
if (Select-String -LiteralPath $sourceFiles -Pattern '(?<![A-Za-z])[A-Za-z]:[\\/]|\.asu_key' -Quiet) {
    throw 'A local absolute path or old private key reference was found in release source. The package was not built.'
}

try {
    & python -m PyInstaller --version *> $null
} catch {
    throw 'PyInstaller is missing. Run: python -m pip install pyinstaller==6.22.3'
}
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is missing. Run: python -m pip install pyinstaller==6.22.3'
}

Push-Location $projectRoot
try {
    & python -m PyInstaller `
        --noconfirm `
        --onefile `
        --noconsole `
        --name BusinessLiteratureRadar `
        --distpath $distDir `
        --workpath $buildDir `
        --specpath $buildDir `
        --add-data "$projectRoot\web;web" `
        --hidden-import search_papers `
        --hidden-import search_v2 `
        --hidden-import agent_bridge `
        app.py
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $exePath)) {
        throw 'PyInstaller did not produce BusinessLiteratureRadar.exe.'
    }

    $stage = Join-Path $distDir ('stage-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        $files = @(
            'BusinessLiteratureRadar.exe', 'run.bat', 'run.sh', 'app.py',
            'agent_bridge.py', 'app_settings.py', 'search_papers.py', 'search_v2.py',
            'requirements.txt', 'README.md', 'README.en.md', 'LICENSE'
        )
        foreach ($file in $files) {
            $source = if ($file -eq 'BusinessLiteratureRadar.exe') { $exePath } else { Join-Path $projectRoot $file }
            Copy-Item -LiteralPath $source -Destination (Join-Path $stage $file)
        }
        foreach ($dir in @('web', '.agents', '.claude', 'docs')) {
            $source = Join-Path $projectRoot $dir
            if (Test-Path -LiteralPath $source) {
                Copy-Item -LiteralPath $source -Destination (Join-Path $stage $dir) -Recurse
            }
        }
        if (Test-Path -LiteralPath $zipPath) {
            throw "Release archive already exists: $zipPath. Choose another version or remove that archive explicitly."
        }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory(
            $stage,
            $zipPath,
            [System.IO.Compression.CompressionLevel]::Optimal,
            $false
        )
    } finally {
        $resolvedStage = (Resolve-Path -LiteralPath $stage).Path
        $resolvedDist = (Resolve-Path -LiteralPath $distDir).Path
        if ($resolvedStage.StartsWith($resolvedDist + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedStage -Recurse -Force
        }
    }

    Write-Host "Created $zipPath"
    Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath | Format-Table Hash, Path -AutoSize
} finally {
    Pop-Location
}
