[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$root = Split-Path -Parent $PSScriptRoot
$encoding = [Text.UTF8Encoding]::new($false)
$requiredFields = @(
    'id',
    'title',
    'aliases',
    'domain',
    'note_type',
    'attack_phase',
    'status',
    'tags',
    'updated'
)

function Remove-FencedCode {
    param([string]$Text)

    $insideFence = $false
    $result = [Collections.Generic.List[string]]::new()
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line -match '^\s*(```|~~~)') {
            $insideFence = -not $insideFence
            continue
        }
        if (-not $insideFence) {
            $result.Add($line)
        }
    }
    return $result -join "`n"
}

$files = @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.md')
$errors = [Collections.Generic.List[string]]::new()
$warnings = [Collections.Generic.List[string]]::new()
$ids = @{}
$incoming = @{}
$byBaseName = @{}

foreach ($file in $files) {
    $key = $file.FullName.ToLowerInvariant()
    $incoming[$key] = 0
    if (-not $byBaseName.ContainsKey($file.BaseName)) {
        $byBaseName[$file.BaseName] = [Collections.Generic.List[IO.FileInfo]]::new()
    }
    $byBaseName[$file.BaseName].Add($file)
}

foreach ($file in $files) {
    $relative = $file.FullName.Substring($root.Length + 1)
    $text = [IO.File]::ReadAllText($file.FullName, $encoding)
    $lines = $text -split "`r?`n"
    for ($lineNumber = 0; $lineNumber -lt $lines.Count; $lineNumber++) {
        if ($lines[$lineNumber] -match '[ \t]+$') {
            $errors.Add("存在尾随空格：${relative}:$($lineNumber + 1)")
        }
    }
    if (-not ($text.EndsWith("`n"))) {
        $errors.Add("文件末尾缺少换行：$relative")
    }
    if ($text -notmatch '(?s)^---\r?\n(.*?)\r?\n---\r?\n') {
        $errors.Add("缺少或无法解析 Front Matter：$relative")
        continue
    }

    $frontMatter = $Matches[1]
    foreach ($field in $requiredFields) {
        if ($frontMatter -notmatch "(?m)^$([regex]::Escape($field)):\s*") {
            $errors.Add("缺少元数据字段 $field：$relative")
        }
    }

    if ($frontMatter -match '(?m)^id:\s*([^\r\n]+)') {
        $id = $Matches[1].Trim().Trim("'")
        if ($ids.ContainsKey($id)) {
            $errors.Add("重复 id ${id}：${relative}；$($ids[$id])")
        } else {
            $ids[$id] = $relative
        }
    }

    $outsideLines = [Collections.Generic.List[string]]::new()
    $insideFence = $false
    $fenceMarker = ''
    foreach ($lineNumber in 0..($lines.Count - 1)) {
        $line = $lines[$lineNumber]
        if (-not $insideFence -and $line -match '^\s*(```|~~~)(.*)$') {
            $insideFence = $true
            $fenceMarker = $Matches[1]
            if ([string]::IsNullOrWhiteSpace($Matches[2])) {
                $errors.Add("代码围栏缺少语言：${relative}:$($lineNumber + 1)")
            }
            continue
        }
        if ($insideFence -and $line -match ('^\s*' + [regex]::Escape($fenceMarker) + '\s*$')) {
            $insideFence = $false
            $fenceMarker = ''
            continue
        }
        if (-not $insideFence) {
            $outsideLines.Add($line)
        }
    }
    if ($insideFence) {
        $errors.Add("代码围栏未闭合：$relative")
    }

    $outsideCode = $outsideLines -join "`n"
    $h1Matches = @([regex]::Matches($outsideCode, '(?m)^#\s+(.+?)\s*$'))
    if ($h1Matches.Count -eq 0) {
        $errors.Add("缺少 H1：$relative")
    } elseif ($h1Matches.Count -gt 1) {
        $errors.Add("存在多个 H1：$relative")
    }
    if ($frontMatter -match "(?m)^title:\s*'?([^'\r\n]+)'?\s*$" -and $h1Matches.Count -gt 0) {
        $frontTitle = $Matches[1].Trim()
        $h1Title = $h1Matches[0].Groups[1].Value.Trim()
        if ($frontTitle -ne $h1Title) {
            $errors.Add("title 与 H1 不一致：$relative")
        }
    }

    $previousLevel = 0
    foreach ($heading in [regex]::Matches($outsideCode, '(?m)^(#{1,6})\s+\S')) {
        $currentLevel = $heading.Groups[1].Value.Length
        if ($previousLevel -gt 0 -and $currentLevel -gt ($previousLevel + 1)) {
            $errors.Add("标题层级跳跃：$relative")
            break
        }
        $previousLevel = $currentLevel
    }

    foreach ($match in [regex]::Matches($outsideCode, '\[\[([^\]|#]+)')) {
        $target = $match.Groups[1].Value.Trim()
        $localTarget = Join-Path $file.DirectoryName ($target -replace '/', '\')
        if (Test-Path -LiteralPath $localTarget) {
            if ([IO.Path]::GetExtension($localTarget) -eq '.md') {
                $incoming[[IO.Path]::GetFullPath($localTarget).ToLowerInvariant()]++
            }
        } elseif ($byBaseName.ContainsKey($target) -and $byBaseName[$target].Count -eq 1) {
            $targetFile = $byBaseName[$target][0]
            $incoming[$targetFile.FullName.ToLowerInvariant()]++
        } elseif (-not $byBaseName.ContainsKey($target)) {
            $warnings.Add("未解析 Wiki 链接：$relative -> [[$target]]")
        } else {
            $warnings.Add("同名 Wiki 链接存在歧义：$relative -> [[$target]]")
        }
    }

    foreach ($match in [regex]::Matches($outsideCode, '\[[^\]]+\]\((?:<([^>]+)>|([^\)]+))\)')) {
        $target = if ($match.Groups[1].Success) { $match.Groups[1].Value } else { $match.Groups[2].Value }
        $target = $target.Trim()
        if ($target -match '^(https?|mailto|javascript):' -or $target.StartsWith('#')) {
            continue
        }
        $target = ($target -split '#', 2)[0]
        try {
            $decoded = [Uri]::UnescapeDataString($target)
            $resolved = [IO.Path]::GetFullPath((Join-Path $file.DirectoryName ($decoded -replace '/', '\')))
        } catch {
            $warnings.Add("无法规范化链接：$relative -> $target")
            continue
        }
        if (-not (Test-Path -LiteralPath $resolved)) {
            $errors.Add("断开的内部链接：$relative -> $target")
        } elseif ([IO.Path]::GetExtension($resolved) -eq '.md') {
            $incoming[$resolved.ToLowerInvariant()]++
        }
    }
}

$contentNotes = @($files | Where-Object {
    $_.Name -ne 'README.md' -and
    $_.Name -ne '_index.md' -and
    $_.Directory.Name -notin @('_索引', '_模板', '_规范')
})
$orphans = @($contentNotes | Where-Object { $incoming[$_.FullName.ToLowerInvariant()] -eq 0 })
foreach ($orphan in $orphans) {
    $errors.Add("未被索引或其他笔记引用：$($orphan.FullName.Substring($root.Length + 1))")
}

Write-Host "Markdown 文件：$($files.Count)"
Write-Host "内容笔记：$($contentNotes.Count)"
Write-Host "唯一元数据 ID：$($ids.Count)"
Write-Host "孤立内容笔记：$($orphans.Count)"
Write-Host "错误：$($errors.Count)"
Write-Host "警告：$($warnings.Count)"

if ($warnings.Count -gt 0) {
    Write-Host "`n警告："
    $warnings | Sort-Object -Unique | ForEach-Object { Write-Host "- $_" }
}

if ($errors.Count -gt 0) {
    Write-Host "`n错误："
    $errors | Sort-Object -Unique | ForEach-Object { Write-Host "- $_" }
    exit 1
}

Write-Host "`n知识库检查通过。"
