$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDirectory "common.ps1")

function Assert-Equal {
    param(
        [Parameter(Mandatory)]
        [AllowNull()]
        [object]$Expected,

        [Parameter(Mandatory)]
        [AllowNull()]
        [object]$Actual,

        [Parameter(Mandatory)]
        [string]$Message
    )

    if ($Expected -ne $Actual) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

$phaseResponse = [pscustomobject]@{
    answers = [pscustomobject]@{
        phase = [pscustomobject]@{
            choice = "blocked"
            confidence = 0.93
        }
        kind = [pscustomobject]@{
            choice = "bug"
            confidence = 0.99
        }
    }
}
$phaseDecision = Resolve-TitleDecision -Response $phaseResponse
Assert-Equal -Expected "blocked" -Actual $phaseDecision.label -Message "Phase must take precedence."
Assert-Equal -Expected "⏸" -Actual $phaseDecision.prefix -Message "Blocked prefix mismatch."

$kindResponse = [pscustomobject]@{
    answers = [pscustomobject]@{
        phase = [pscustomobject]@{
            choice = "wip"
            confidence = 0.42
        }
        kind = [pscustomobject]@{
            choice = "feature"
            confidence = 0.88
        }
    }
}
$kindDecision = Resolve-TitleDecision -Response $kindResponse
Assert-Equal -Expected "feature" -Actual $kindDecision.label -Message "Kind fallback mismatch."
Assert-Equal -Expected "✨" -Actual $kindDecision.prefix -Message "Feature prefix mismatch."

$uncertainResponse = [pscustomobject]@{
    answers = [pscustomobject]@{
        phase = [pscustomobject]@{
            choice = "unknown"
            confidence = 0.98
        }
        kind = [pscustomobject]@{
            choice = "chat"
            confidence = 0.31
        }
    }
}
$uncertainDecision = Resolve-TitleDecision -Response $uncertainResponse
Assert-Equal -Expected $null -Actual $uncertainDecision -Message "Uncertain decisions must not rename."

$continuation = New-RenameContinuation -SessionId "thread-123" -Prefix "✅" -Label "done"
if (-not $continuation.StartsWith("[thread-title-organizer]", [StringComparison]::Ordinal)) {
    throw "Continuation marker is missing."
}
if ($continuation -notmatch "Do not modify any other thread") {
    throw "Continuation scope guard is missing."
}

$request = New-JevRequest -UserPrompt "Implement the feature." -AssistantMessage "Implementation is complete."
Assert-Equal -Expected "jev-latest" -Actual $request.model -Message "Default model mismatch."
Assert-Equal -Expected 2 -Actual $request.questions.Count -Message "Jev questions must be batched."

[Console]::Out.WriteLine("Contract tests passed.")
