$ErrorActionPreference = 'Continue'
$bin = Join-Path $env:LOCALAPPDATA 'Programs\KiroCrew\resources\backend-dist\kirocrew-backend\bin'
$out = Join-Path $PSScriptRoot 'kc_result.txt'
Remove-Item $out -ErrorAction SilentlyContinue

# 1) Confirm persistent User PATH contains bin
$userPath = [Environment]::GetEnvironmentVariable('Path','User')
if ($userPath -like "*$bin*") { "USER_PATH: present" | Out-File $out }
else { "USER_PATH: MISSING" | Out-File $out }

# 2) Make it usable in THIS session too
if ($env:Path -notlike "*$bin*") { $env:Path = $env:Path.TrimEnd(';') + ';' + $bin }

# resolve the command via PATH (proves PATH works)
$cmd = (Get-Command kirocrew -ErrorAction SilentlyContinue)
if ($cmd) { "RESOLVED: $($cmd.Source)" | Out-File $out -Append }
else { "RESOLVED: NOT FOUND on PATH" | Out-File $out -Append }

function Run-WithTimeout($argList, $label, $timeoutSec) {
    "=== $label ===" | Out-File $out -Append
    $tmp = [System.IO.Path]::GetTempFileName()
    $exe = Join-Path $bin 'kirocrew.cmd'
    $p = Start-Process -FilePath $exe -ArgumentList $argList -NoNewWindow -PassThru -RedirectStandardOutput $tmp -RedirectStandardError "$tmp.err"
    if ($p.WaitForExit($timeoutSec * 1000)) {
        Get-Content $tmp -ErrorAction SilentlyContinue | Out-File $out -Append
        Get-Content "$tmp.err" -ErrorAction SilentlyContinue | Out-File $out -Append
        "EXIT=$($p.ExitCode)" | Out-File $out -Append
    } else {
        try { $p.Kill() } catch {}
        Get-Content $tmp -ErrorAction SilentlyContinue | Out-File $out -Append
        Get-Content "$tmp.err" -ErrorAction SilentlyContinue | Out-File $out -Append
        "TIMEOUT after $timeoutSec s (killed)" | Out-File $out -Append
    }
    Remove-Item $tmp,"$tmp.err" -ErrorAction SilentlyContinue
}

Run-WithTimeout @('config','set','--local','agent.spawn_min_memory_gb','1.0') 'config set --local agent.spawn_min_memory_gb 1.0' 30
Run-WithTimeout @('config','get','agent.spawn_min_memory_gb') 'config get agent.spawn_min_memory_gb' 30

"DONE" | Out-File $out -Append
