param(
    [string]$Source,
    [ValidateSet("auto", "openai", "disabled")]
    [string]$Provider = "auto",
    [string]$Model = "gpt-4.1-mini",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not $Source) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $candidate = Get-ChildItem -Path $desktop -Recurse -Filter "sales *demo.xlsx" |
        Where-Object { $_.FullName -like "*ads_rpt_sal_ncs_register_to_order_sales_ssa_t_202605151845*" } |
        Select-Object -First 1
    if (-not $candidate) {
        throw "Default source workbook was not found. Pass -Source with the workbook path."
    }
    $Source = $candidate.FullName
}

$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path -LiteralPath $bundledPython) {
    $pythonExe = $bundledPython
} else {
    $pythonExe = "python"
}

$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
$env:BA_AGENT_LLM_PROVIDER = $Provider
$env:BA_AGENT_OPENAI_MODEL = $Model

if ($Provider -eq "openai" -and -not $env:OPENAI_API_KEY) {
    $secureKey = Read-Host "OpenAI API key" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

& $pythonExe -m ba_analysis_agent.web_app --source $Source --port $Port
