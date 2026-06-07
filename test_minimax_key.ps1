param(
    [string]$Model = "MiniMax-M2.7",
    [ValidateSet("sdk", "anthropic", "openai", "both")]
    [string]$Protocol = "both",
    [string]$OpenAIBaseUrl = "https://api.minimaxi.com/v1",
    [string]$AnthropicBaseUrl = "https://api.minimax.io/anthropic"
)

$ErrorActionPreference = "Stop"

function Read-SecretText($Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Clean-ApiKey($Value) {
    $key = $Value.Trim()
    if ($key.ToLowerInvariant().StartsWith("bearer ")) {
        $key = $key.Substring(7).Trim()
    }
    return ($key -replace "\s", "")
}

$token = Clean-ApiKey (Read-SecretText "MiniMax API token")
if (-not $token) {
    throw "Token is empty."
}

try {
    [Text.Encoding]::ASCII.GetBytes($token) | Out-Null
} catch {
    throw "Token contains non-ASCII characters. Paste the raw MiniMax token only."
}

function Show-Error($ErrorRecord) {
    Write-Host $ErrorRecord.Exception.Message
    if ($ErrorRecord.ErrorDetails.Message) {
        Write-Host $ErrorRecord.ErrorDetails.Message
    }
}

function Test-OpenAICompatible {
    Write-Host "Testing MiniMax OpenAI-compatible chat completion..." -ForegroundColor Cyan
    $headers = @{
        Authorization = "Bearer $token"
        "Content-Type" = "application/json"
    }
    $body = @{
        model = $Model
        messages = @(
            @{ role = "system"; content = "You are a helpful assistant." },
            @{ role = "user"; content = "Reply with exactly: OK" }
        )
        temperature = 0.2
        max_completion_tokens = 32
    } | ConvertTo-Json -Depth 8

    try {
        $response = Invoke-RestMethod `
            -Method Post `
            -Uri "$OpenAIBaseUrl/chat/completions" `
            -Headers $headers `
            -Body $body
        Write-Host "OpenAI-compatible chat completion: OK" -ForegroundColor Green
        $response.choices[0].message.content
    } catch {
        Write-Host "OpenAI-compatible chat completion failed:" -ForegroundColor Red
        Show-Error $_
    }
}

function Test-AnthropicCompatible {
    Write-Host "Testing MiniMax Anthropic-compatible messages..." -ForegroundColor Cyan
    $headers = @{
        "X-Api-Key" = $token
        "Content-Type" = "application/json"
    }
    $body = @{
        model = $Model
        max_tokens = 32
        temperature = 0.2
        system = "You are a helpful assistant."
        messages = @(
            @{ role = "user"; content = "Reply with exactly: OK" }
        )
    } | ConvertTo-Json -Depth 8

    try {
        $response = Invoke-RestMethod `
            -Method Post `
            -Uri "$AnthropicBaseUrl/v1/messages" `
            -Headers $headers `
            -Body $body
        Write-Host "Anthropic-compatible messages: OK" -ForegroundColor Green
        ($response.content | Where-Object { $_.type -eq "text" } | Select-Object -First 1).text
    } catch {
        Write-Host "Anthropic-compatible messages failed:" -ForegroundColor Red
        Show-Error $_
    }
}

function Test-AnthropicSdk {
    Write-Host "Testing MiniMax via Anthropic SDK..." -ForegroundColor Cyan
    $python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        $python = "python"
    }
    $env:ANTHROPIC_API_KEY = $token
    $env:ANTHROPIC_BASE_URL = $AnthropicBaseUrl
    $env:MINIMAX_TEST_MODEL = $Model
    $script = @'
import os
try:
    from anthropic import Anthropic
except ImportError:
    raise SystemExit("anthropic package is not installed. Run: python -m pip install anthropic")

client = Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    base_url=os.environ["ANTHROPIC_BASE_URL"],
)
message = client.messages.create(
    model=os.environ.get("MINIMAX_TEST_MODEL", "MiniMax-M2.7"),
    max_tokens=32,
    temperature=0.2,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": [{"type": "text", "text": "Reply with exactly: OK"}]},
    ],
)
for block in message.content:
    if getattr(block, "type", None) == "text":
        print(block.text)
        break
'@
    try {
        $script | & $python -
        Write-Host "Anthropic SDK: OK" -ForegroundColor Green
    } catch {
        Write-Host "Anthropic SDK failed:" -ForegroundColor Red
        Show-Error $_
    }
}

if ($Protocol -eq "sdk") {
    Test-AnthropicSdk
    exit
}

if ($Protocol -in @("openai", "both")) {
    Test-OpenAICompatible
}

if ($Protocol -in @("anthropic", "both")) {
    Test-AnthropicCompatible
}

if ($Protocol -eq "both") {
    Test-AnthropicSdk
}
