$scriptPath = Join-Path $PSScriptRoot '..\install_spina_pc.ps1'
$tokens = $null
$errors = $null
$tree = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) { throw "Installer script could not be parsed." }
$function = $tree.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Resolve-SafePortalUri' }, $true)
if ($null -eq $function) { throw "Resolve-SafePortalUri function is missing." }
. ([scriptblock]::Create($function.Extent.Text))

$accepted = @(
    @('https://spina.test', 'https://spina.test'),
    @('http://localhost:8000', 'http://localhost:8000'),
    @('http://127.0.0.1:8000', 'http://127.0.0.1:8000'),
    @('http://[::1]:8000', 'http://[::1]:8000'),
    @('http://[0:0:0:0:0:0:0:1]:8000', 'http://[::1]:8000'),
    @('http://127.0.0.2:8000', 'http://127.0.0.2:8000')
)
foreach ($case in $accepted) {
    $actual = Resolve-SafePortalUri -Value $case[0]
    # Windows .NET Framework expands IPv6 text; compare its canonical URI.
    $expected = ([System.Uri]::new($case[1])).AbsoluteUri.TrimEnd("/")
    if ($actual -ne $expected) { throw "Unexpected normalized URL for $($case[0]): $actual" }
}

$rejected = @(
    'ftp://localhost/demo',
    'file://localhost/C:/demo',
    'http://spina.test',
    'http://10.0.0.1:8000',
    'http://[::2]:8000',
    'http://0.0.0.0:8000',
    'http://localhost.example:8000'
)
foreach ($value in $rejected) {
    $didReject = $false
    try { $null = Resolve-SafePortalUri -Value $value }
    catch { $didReject = $true }
    if (-not $didReject) { throw "Unsupported portal URL was accepted: $value" }
}
Write-Output "$($accepted.Count + $rejected.Count) portal URL cases passed."
