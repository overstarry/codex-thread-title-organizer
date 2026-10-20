Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$script:KnownPrefixes = @(
    "⏸",
    "👀",
    "✅",
    "🚧",
    "💡",
    "🐛",
    "💬",
    "🎨",
    "✨",
    "🛠️"
)

$script:PrefixByLabel = @{
    blocked  = "⏸"
    validate = "👀"
    done     = "✅"
    wip      = "🚧"
    plan     = "💡"
    bug      = "🐛"
    chat     = "💬"
    art      = "🎨"
    feature  = "✨"
    ops      = "🛠️"
}

function Write-HookJson {
    param(
        [Parameter(Mandatory)]
        [hashtable]$Value
    )

    $json = $Value | ConvertTo-Json -Depth 12 -Compress
    [Console]::Out.WriteLine($json)
}

function Write-HookDiagnostic {
    param(
        [Parameter(Mandatory)]
        [string]$Message
    )

    [Console]::Error.WriteLine("thread-title-organizer: $Message")
}

function Get-SafeSessionId {
    param(
        [Parameter(Mandatory)]
        [string]$SessionId
    )

    return $SessionId -replace "[^A-Za-z0-9._-]", "_"
}

function Get-SessionStatePath {
    param(
        [Parameter(Mandatory)]
        [string]$PluginData,

        [Parameter(Mandatory)]
        [string]$SessionId
    )

    $safeSessionId = Get-SafeSessionId -SessionId $SessionId
    return Join-Path (Join-Path $PluginData "sessions") "$safeSessionId.json"
}

function Read-SessionState {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @{}
    }

    $content = Get-Content -LiteralPath $Path -Raw -Encoding utf8
    if ([string]::IsNullOrWhiteSpace($content)) {
        return @{}
    }

    return $content | ConvertFrom-Json -AsHashtable
}

function Write-SessionState {
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [hashtable]$State
    )

    $directory = Split-Path -Parent $Path
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null

    $temporaryPath = "$Path.$([Guid]::NewGuid().ToString("N")).tmp"
    try {
        $json = $State | ConvertTo-Json -Depth 12
        [System.IO.File]::WriteAllText(
            $temporaryPath,
            $json,
            [System.Text.UTF8Encoding]::new($false)
        )
        Move-Item -LiteralPath $temporaryPath -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
}

function Limit-Text {
    param(
        [AllowNull()]
        [string]$Value,

        [int]$MaximumLength = 8000
    )

    if ([string]::IsNullOrEmpty($Value) -or $Value.Length -le $MaximumLength) {
        return $Value
    }

    return $Value.Substring(0, $MaximumLength)
}

function New-JevRequest {
    param(
        [Parameter(Mandatory)]
        [string]$UserPrompt,

        [AllowNull()]
        [string]$AssistantMessage,

        [string]$Model = "jev-latest"
    )

    return @{
        state = @{
            user_prompt      = Limit-Text -Value $UserPrompt
            assistant_message = Limit-Text -Value $AssistantMessage
        }
        model = $Model
        questions = @{
            phase = @{
                type = "choice"
                instructions = "Which single workflow phase best describes the thread after the assistant response? Prefer explicit evidence in assistant_message. When several apply, use this precedence: blocked, validate, done, wip, plan, unknown."
                criteria = @{
                    blocked = "Progress cannot continue without user input, approval, credentials, or an external state change. Do not use for ordinary uncertainty."
                    validate = "Implementation or analysis is complete enough to await review, acceptance, or verification."
                    done = "The requested work is complete and the assistant reports the result, including any bounded limitations."
                    wip = "The assistant is actively implementing, investigating, or executing the requested work."
                    plan = "The thread is primarily planning, designing, researching, or evaluating options before implementation."
                    unknown = "No workflow phase is supported strongly enough by the supplied state."
                }
            }
            kind = @{
                type = "choice"
                instructions = "What is the primary task kind in user_prompt and assistant_message? Choose the closest durable category, or unknown when none fits."
                criteria = @{
                    bug = "Diagnosing or fixing incorrect behavior, failures, regressions, crashes, or performance defects."
                    chat = "General discussion, question answering, explanation, or advice without a more specific production task."
                    art = "Creating or editing visual design, images, illustrations, branding, or other creative media."
                    feature = "Building or extending product behavior, application code, integrations, or automation."
                    ops = "Infrastructure, deployment, runtime operations, observability, configuration, or incident response."
                    unknown = "No task kind is supported strongly enough by the supplied state."
                }
            }
        }
    }
}

function Invoke-JevClassification {
    param(
        [Parameter(Mandatory)]
        [hashtable]$Request,

        [Parameter(Mandatory)]
        [string]$ApiKey
    )

    $headers = @{
        Authorization = "Bearer $ApiKey"
    }
    $body = $Request | ConvertTo-Json -Depth 12 -Compress

    $maximumAttempts = 2
    for ($attempt = 1; $attempt -le $maximumAttempts; $attempt++) {
        try {
            return Invoke-RestMethod `
                -Method Post `
                -Uri "https://api.typesafe.ai/v1/systemone" `
                -Headers $headers `
                -ContentType "application/json" `
                -Body $body `
                -HttpVersion "1.1" `
                -TimeoutSec 12
        }
        catch {
            $statusCode = $null
            $responseProperty = $_.Exception.PSObject.Properties["Response"]
            if ($null -ne $responseProperty -and $null -ne $responseProperty.Value) {
                $statusCode = [int]$responseProperty.Value.StatusCode
            }

            $isNonRetryable = $statusCode -in @(400, 401, 403, 404, 422)
            if ($isNonRetryable -or $attempt -eq $maximumAttempts) {
                throw
            }

            Start-Sleep -Milliseconds 300
        }
    }
}

function Resolve-TitleDecision {
    param(
        [Parameter(Mandatory)]
        [object]$Response,

        [double]$PhaseConfidenceThreshold = 0.80,

        [double]$KindConfidenceThreshold = 0.75
    )

    $phase = $Response.answers.phase
    if (
        $null -ne $phase -and
        $phase.choice -ne "unknown" -and
        [double]$phase.confidence -ge $PhaseConfidenceThreshold -and
        $script:PrefixByLabel.ContainsKey([string]$phase.choice)
    ) {
        return @{
            label      = [string]$phase.choice
            prefix     = $script:PrefixByLabel[[string]$phase.choice]
            confidence = [double]$phase.confidence
            source     = "phase"
        }
    }

    $kind = $Response.answers.kind
    if (
        $null -ne $kind -and
        $kind.choice -ne "unknown" -and
        [double]$kind.confidence -ge $KindConfidenceThreshold -and
        $script:PrefixByLabel.ContainsKey([string]$kind.choice)
    ) {
        return @{
            label      = [string]$kind.choice
            prefix     = $script:PrefixByLabel[[string]$kind.choice]
            confidence = [double]$kind.confidence
            source     = "kind"
        }
    }

    return $null
}

function New-RenameContinuation {
    param(
        [Parameter(Mandatory)]
        [string]$SessionId,

        [Parameter(Mandatory)]
        [string]$Prefix,

        [Parameter(Mandatory)]
        [string]$Label
    )

    $knownPrefixes = $script:KnownPrefixes -join " "
    return "[thread-title-organizer] Use the native Codex thread tools only. For the current root thread with session id '$SessionId', read its current title, remove all leading organizer prefixes from this set: $knownPrefixes, then prepend exactly '$Prefix ' to the remaining title. Keep the remaining title text unchanged. If the title already has exactly that normalized prefix, do nothing. Do not modify any other thread. This classification is '$Label'. After the tool call, finish without an explanatory message."
}
