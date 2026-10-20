$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDirectory "common.ps1")

if ([string]::IsNullOrWhiteSpace([string]$env:TYPESAFE_API_KEY)) {
    throw "TYPESAFE_API_KEY is not set."
}

$request = New-JevRequest `
    -UserPrompt "Implement the agreed Codex thread title plugin using Jev." `
    -AssistantMessage "The implementation is complete and the contract tests passed."
$response = Invoke-JevClassification -Request $request -ApiKey ([string]$env:TYPESAFE_API_KEY)
$decision = Resolve-TitleDecision -Response $response

if ($null -eq $decision) {
    throw "Jev returned no actionable title decision for the live fixture."
}

[pscustomobject]@{
    model = $response.model
    phase = $response.answers.phase.choice
    phase_confidence = $response.answers.phase.confidence
    kind = $response.answers.kind.choice
    kind_confidence = $response.answers.kind.confidence
    selected_label = $decision.label
    selected_prefix = $decision.prefix
} | ConvertTo-Json -Compress
