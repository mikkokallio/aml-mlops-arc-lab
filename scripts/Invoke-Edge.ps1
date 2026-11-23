[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Script,
    [string]$EvidenceName = 'edge-command'
)

$ErrorActionPreference = 'Stop'
$directory = Join-Path $PSScriptRoot '..\.local'
$temporaryScript = Join-Path $directory ("run-" + [guid]::NewGuid().ToString('N') + '.sh')
$content = (Get-Content -LiteralPath $Script -Raw).Replace("`r", '')
$content = "#!/bin/sh`nexec /bin/bash <<'LAB_REMOTE_SCRIPT'`nset -euo pipefail`n" + $content + "`necho LAB_COMMAND_SUCCEEDED`nLAB_REMOTE_SCRIPT`n"
[System.IO.File]::WriteAllText($temporaryScript, $content, [System.Text.UTF8Encoding]::new($false))
try {
    $result = & az vm run-command invoke --resource-group rg-amlarclab-edge --name amlarclab-edge --command-id RunShellScript --scripts "@$temporaryScript" --output json
    if ($LASTEXITCODE -ne 0) { throw 'VM Run Command management operation failed.' }
    $result | Set-Content -LiteralPath (Join-Path $directory "$EvidenceName.json")
    $response = ($result -join "`n") | ConvertFrom-Json
    $messages = ($response.value.message -join "`n")
    Write-Output $messages
    if (-not $messages.Contains('LAB_COMMAND_SUCCEEDED')) {
        throw 'Remote script did not complete successfully. See the saved evidence.'
    }
}
finally {
    Remove-Item -LiteralPath $temporaryScript
}
