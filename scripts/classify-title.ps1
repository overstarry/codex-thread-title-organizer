$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDirectory "common.ps1")

try {
    $rawInput = [Console]::In.ReadToEnd()
    $hookInput = $rawInput | ConvertFrom-Json -AsHashtable

    if ([bool]$hookInput.stop_hook_active) {
        Write-HookJson -Value @{ continue = $true }
        exit 0
    }

    $sessionId = [string]$hookInput.session_id
    $pluginData = [string]$env:PLUGIN_DATA
    if ([string]::IsNullOrWhiteSpace($sessionId) -or [string]::IsNullOrWhiteSpace($pluginData)) {
        Write-HookJson -Value @{ continue = $true }
        exit 0
    }

    $statePath = Get-SessionStatePath -PluginData $pluginData -SessionId $sessionId
    $state = Read-SessionState -Path $statePath
    if (-not $state.ContainsKey("prompt") -or [string]::IsNullOrWhiteSpace([string]$state.prompt)) {
        Write-HookJson -Value @{ continue = $true }
        exit 0
    }

    $apiKey = [string]$env:TYPESAFE_API_KEY
    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        throw "TYPESAFE_API_KEY is not set."
    }

    $model = if ([string]::IsNullOrWhiteSpace([string]$env:TYPESAFE_MODEL)) {
        "jev-latest"
    }
    else {
        [string]$env:TYPESAFE_MODEL
    }

    $request = New-JevRequest `
        -UserPrompt ([string]$state.prompt) `
        -AssistantMessage ([string]$hookInput.last_assistant_message) `
        -Model $model
    $response = Invoke-JevClassification -Request $request -ApiKey $apiKey
    $decision = Resolve-TitleDecision -Response $response

    $state.last_model = [string]$response.model
    $state.last_classified_at = [DateTimeOffset]::UtcNow.ToString("O")
    if ($null -eq $decision) {
        $state.last_outcome = "no_change"
        Write-SessionState -Path $statePath -State $state
        Write-HookJson -Value @{ continue = $true }
        exit 0
    }

    if (
        $state.ContainsKey("last_requested_label") -and
        [string]$state.last_requested_label -eq [string]$decision.label
    ) {
        $state.last_outcome = "unchanged"
        Write-SessionState -Path $statePath -State $state
        Write-HookJson -Value @{ continue = $true }
        exit 0
    }

    $state.last_requested_label = [string]$decision.label
    $state.last_requested_prefix = [string]$decision.prefix
    $state.last_confidence = [double]$decision.confidence
    $state.last_decision_source = [string]$decision.source
    $state.last_outcome = "rename_requested"
    Write-SessionState -Path $statePath -State $state

    $reason = New-RenameContinuation `
        -SessionId $sessionId `
        -Prefix ([string]$decision.prefix) `
        -Label ([string]$decision.label)
    Write-HookJson -Value @{
        decision = "block"
        reason   = $reason
    }
}
catch {
    Write-HookDiagnostic -Message $_.Exception.Message
    Write-HookJson -Value @{ continue = $true }
}

exit 0
