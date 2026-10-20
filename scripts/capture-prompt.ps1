$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDirectory "common.ps1")

try {
    $rawInput = [Console]::In.ReadToEnd()
    $hookInput = $rawInput | ConvertFrom-Json -AsHashtable

    $sessionId = [string]$hookInput.session_id
    $prompt = [string]$hookInput.prompt
    if ([string]::IsNullOrWhiteSpace($sessionId) -or [string]::IsNullOrWhiteSpace($prompt)) {
        exit 0
    }

    if ($prompt.StartsWith("[thread-title-organizer]", [StringComparison]::Ordinal)) {
        exit 0
    }

    $pluginData = [string]$env:PLUGIN_DATA
    if ([string]::IsNullOrWhiteSpace($pluginData)) {
        throw "PLUGIN_DATA is not set."
    }

    $statePath = Get-SessionStatePath -PluginData $pluginData -SessionId $sessionId
    $state = Read-SessionState -Path $statePath
    $state.session_id = $sessionId
    $state.prompt = $prompt
    $state.captured_at = [DateTimeOffset]::UtcNow.ToString("O")
    Write-SessionState -Path $statePath -State $state
}
catch {
    Write-HookDiagnostic -Message $_.Exception.Message
}

exit 0
