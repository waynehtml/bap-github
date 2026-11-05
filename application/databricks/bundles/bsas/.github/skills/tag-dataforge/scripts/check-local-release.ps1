[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$stableSemVerCore =
    "(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
$stableSemVerPattern = "^$stableSemVerCore$"

function Invoke-Git {
    param([Parameter(Mandatory)][string[]] $Arguments)

    $output = & git @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    if ($exitCode -ne 0) {
        $safeText = $text -replace "(?i)(https?://)[^/@\s]+@", '$1***@'
        throw "git $($Arguments[0]) failed: $safeText"
    }
    return $text.Trim()
}

function Get-SingleMatchValue {
    param(
        [Parameter(Mandatory)][string] $Text,
        [Parameter(Mandatory)][string] $Pattern,
        [Parameter(Mandatory)][string] $Label
    )

    $matches = [regex]::Matches(
        $Text,
        $Pattern,
        [System.Text.RegularExpressions.RegexOptions]::Multiline
    )
    if ($matches.Count -ne 1) {
        throw "$Label must appear exactly once."
    }
    return $matches[0].Groups[1].Value
}

function Assert-StableSemVer {
    param(
        [Parameter(Mandatory)][string] $Value,
        [Parameter(Mandatory)][string] $Label
    )

    if ($Value -notmatch $stableSemVerPattern) {
        throw "$Label must be an exact stable MAJOR.MINOR.PATCH value."
    }
}

function Get-NewestChangelogRelease {
    param(
        [Parameter(Mandatory)][string] $Path,
        [Parameter(Mandatory)][string] $ProjectName
    )

    $text = [System.IO.File]::ReadAllText($Path)
    $match = [regex]::Match(
        $text,
        "(?m)^## ([0-9]+\.[0-9]+\.[0-9]+) - " +
            "[0-9]{4}-[0-9]{2}-[0-9]{2}\s*$"
    )
    if (-not $match.Success) {
        throw "$ProjectName changelog has no numbered release section."
    }
    $version = $match.Groups[1].Value
    Assert-StableSemVer -Value $version -Label "$ProjectName changelog version"
    $sections = [regex]::Matches(
        ($text -replace "`r`n", "`n"),
        "(?ms)^## " + [regex]::Escape($version) +
            " - [^\n]*\n.*?(?=^## |\z)"
    )
    if ($sections.Count -ne 1) {
        throw "$ProjectName changelog release section must appear exactly once."
    }
    $section = $sections[0].Value.Trim([char[]]"`r`n")
    if ($section -notmatch '(?m)^[-*] +\S') {
        throw "$ProjectName changelog release section has no change bullets."
    }
    return [ordered]@{ version = $version; section = $section }
}

function Resolve-Provider {
    param([Parameter(Mandatory)][string] $RemoteUrl)

    if ($RemoteUrl -match '^https://github\.com/' -or
        $RemoteUrl -match '^git@github\.com:' -or
        $RemoteUrl -match '^ssh://git@github\.com/') {
        return "GitHub"
    }
    if ($RemoteUrl -match '^https://dev\.azure\.com/' -or
        $RemoteUrl -match '^https://[^/]+\.visualstudio\.com/' -or
        $RemoteUrl -match '^git@ssh\.dev\.azure\.com:v3/' -or
        $RemoteUrl -match '^ssh://git@ssh\.dev\.azure\.com/v3/') {
        return "AzureDevOps"
    }
    throw "origin must be hosted by GitHub or Azure DevOps."
}

function Get-LocalTagState {
    param(
        [Parameter(Mandatory)][string] $TagName,
        [Parameter(Mandatory)][string] $ExpectedCommit,
        [Parameter(Mandatory)][string] $ExpectedAnnotation,
        [Parameter(Mandatory)][string] $Provider
    )

    $tagRef = "refs/tags/$TagName"
    & git show-ref --verify --quiet $tagRef *> $null
    if ($LASTEXITCODE -ne 0) {
        return [ordered]@{
            state = "absent"
            object = $null
        }
    }
    if ($Provider -ne "AzureDevOps") {
        throw "Local tag $tagRef already exists."
    }

    $tagType = Invoke-Git -Arguments @("cat-file", "-t", $tagRef)
    if ($tagType -ne "tag") {
        throw "Local tag $tagRef is not annotated."
    }
    $tagCommit = Invoke-Git -Arguments @("rev-parse", "$tagRef^{}")
    if ($tagCommit -ne $ExpectedCommit) {
        throw "Local tag $tagRef does not resolve to the confirmed commit."
    }

    $annotationOutput = & git for-each-ref "--format=%(contents)" $tagRef 2>&1
    $exitCode = $LASTEXITCODE
    $annotation = ($annotationOutput | ForEach-Object { $_.ToString() }) -join "`n"
    if ($exitCode -ne 0) {
        throw "Could not read the annotation for local tag $tagRef."
    }
    $annotation = $annotation.TrimEnd([char[]]"`r`n")
    if ($annotation -ne $ExpectedAnnotation) {
        throw "Local tag $tagRef does not have the expected annotation."
    }

    return [ordered]@{
        state = "matching"
        object = Invoke-Git -Arguments @("rev-parse", $tagRef)
    }
}

$projectName = "dataforge"
$projectDisplay = "DataForge"
$projectRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "../../../..")
)
if ((Split-Path -Leaf $projectRoot) -ne $projectName) {
    throw "The tag skill must run from the canonical dataforge project."
}

$originalLocation = Get-Location
try {
    Set-Location -LiteralPath $projectRoot
    $manifest = [System.IO.File]::ReadAllText(
        (Join-Path $projectRoot ".dataforge/manifest.yml")
    )
    $templateName = Get-SingleMatchValue `
        -Text $manifest `
        -Pattern '^\s*name:\s*(dataforge)\s*$' `
        -Label "DataForge template name"
    if ($templateName -ne $projectName) {
        throw "DataForge template name must remain dataforge."
    }
    $createdVersion = Get-SingleMatchValue `
        -Text $manifest `
        -Pattern '^\s*created_from_version:\s*["'']([^"'']+)["'']\s*$' `
        -Label "DataForge created_from_version"
    $appliedVersion = Get-SingleMatchValue `
        -Text $manifest `
        -Pattern '^\s*last_applied_version:\s*["'']([^"'']+)["'']\s*$' `
        -Label "DataForge last_applied_version"
    Assert-StableSemVer `
        -Value $createdVersion `
        -Label "DataForge created_from_version"
    Assert-StableSemVer `
        -Value $appliedVersion `
        -Label "DataForge last_applied_version"
    if ($createdVersion -ne $appliedVersion) {
        throw "Canonical DataForge manifest versions must match."
    }
    $changelogRelease = Get-NewestChangelogRelease `
        -Path (Join-Path $projectRoot ".dataforge/CHANGELOG.md") `
        -ProjectName $projectDisplay
    if ($changelogRelease.version -ne $appliedVersion) {
        throw "DataForge manifest and changelog versions do not match."
    }

    $version = $appliedVersion
    $tagName = "releases/dataforge-v$version"
    $annotation = "DataForge release $version`n`n$($changelogRelease.section)"

$null = Invoke-Git -Arguments @("check-ref-format", "refs/tags/$tagName")
$repositoryRoot = Invoke-Git -Arguments @("rev-parse", "--show-toplevel")
$branch = Invoke-Git -Arguments @("branch", "--show-current")
if ($branch -ne "main") {
    throw "$projectDisplay release tags must be created from main."
}
$status = Invoke-Git -Arguments @(
    "status",
    "--porcelain=v1",
    "--untracked-files=all"
)
if (-not [string]::IsNullOrWhiteSpace($status)) {
    throw "$projectDisplay release tags require a clean working tree."
}
$commit = Invoke-Git -Arguments @("rev-parse", "HEAD")
if ($commit -notmatch '^[0-9a-f]{40}$') {
    throw "HEAD did not resolve to a full commit SHA."
}
$origin = Invoke-Git -Arguments @("remote", "get-url", "origin")
$provider = Resolve-Provider -RemoteUrl $origin

$localTag = Get-LocalTagState `
    -TagName $tagName `
    -ExpectedCommit $commit `
    -ExpectedAnnotation $annotation `
    -Provider $provider

[ordered]@{
    localChecks = "passed"
    project = $projectName
    projectName = $projectDisplay
    provider = $provider
    branch = $branch
    commit = $commit
    version = $version
    tag = $tagName
    localTag = $localTag.state
    localTagObject = $localTag.object
    annotation = $annotation
} | ConvertTo-Json -Depth 4
}
finally {
    Set-Location -LiteralPath $originalLocation
}
