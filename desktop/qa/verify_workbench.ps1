param(
    [Parameter(Mandatory)][string]$DesktopExe,
    [Parameter(Mandatory)][string]$PythonExe,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [switch]$CompareStoredRuns
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$desktop = (Resolve-Path -LiteralPath $DesktopExe).Path
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$output = (New-Item -ItemType Directory -Path $OutputDirectory -Force).FullName
$practice = (New-Item -ItemType Directory -Path (Join-Path ([IO.Path]::GetTempPath()) ('CaseProof-DesktopQA-' + [guid]::NewGuid().ToString('N')))).FullName
$priorAppState = $env:CASEPROOF_DESKTOP_STATE_DIR
$env:CASEPROOF_DESKTOP_STATE_DIR = Join-Path $practice 'client-state'
$approvedTitle = '자동차 서류 제출 기한 개정'
$notes = [Collections.Generic.List[string]]::new()
$captures = [Collections.Generic.List[object]]::new()
$comparisonError = $null
$app = $null
$service = $null

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Windows.Forms, System.Drawing
Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class CaseProofQaWindow {
    public struct Rect { public int Left, Top, Right, Bottom; }
    private delegate bool EnumWindowsProc(IntPtr window, IntPtr state);
    [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr state);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll")] private static extern bool AttachThreadInput(uint from, uint to, bool attach);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern bool BringWindowToTop(IntPtr hwnd);
    [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out Rect rect);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr dc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hwnd, IntPtr insertAfter, int x, int y, int width, int height, uint flags);
    [DllImport("dwmapi.dll")] private static extern int DwmGetWindowAttribute(IntPtr hwnd, int attr, out Rect rect, int size);

    public static bool GetVisibleFrame(IntPtr hwnd, out Rect rect) {
        return DwmGetWindowAttribute(hwnd, 9, out rect, Marshal.SizeOf<Rect>()) == 0;
    }

    public static bool Owned(IntPtr hwnd, int expected) {
        uint pid;
        return hwnd != IntPtr.Zero && GetWindowThreadProcessId(hwnd, out pid) != 0 && pid == expected;
    }

    public static IntPtr[] VisibleWindows(int owner) {
        var windows = new List<IntPtr>();
        EnumWindows((wnd, unused) => { if (IsWindowVisible(wnd) && Owned(wnd, owner)) windows.Add(wnd); return true; }, IntPtr.Zero);
        return windows.ToArray();
    }

    public static bool Activate(IntPtr hwnd, int owner) {
        if (!Owned(hwnd, owner)) return false;
        var previous = GetForegroundWindow();
        if (previous == hwnd) return true;
        uint pid;
        uint foregroundThread = GetWindowThreadProcessId(previous, out pid);
        uint ownThread = GetCurrentThreadId();
        bool joined = foregroundThread != 0 && foregroundThread != ownThread && AttachThreadInput(ownThread, foregroundThread, true);
        try { BringWindowToTop(hwnd); SetForegroundWindow(hwnd); }
        finally { if (joined) AttachThreadInput(ownThread, foregroundThread, false); }
        return Owned(GetForegroundWindow(), owner);
    }
}
'@

$priorDpi = [CaseProofQaWindow]::SetThreadDpiAwarenessContext([IntPtr](-4))

function Assert-Qa([bool]$Condition, [string]$Description) {
    if (!$Condition) { throw $Description }
}

function Wait-Qa([string]$Description, [scriptblock]$Probe, [int]$TimeoutSeconds = 18) {
    $elapsed = [Diagnostics.Stopwatch]::StartNew()
    do {
        $value = & $Probe
        if ($value) { return $value }
        Start-Sleep -Milliseconds 100
    } while ($elapsed.Elapsed.TotalSeconds -lt $TimeoutSeconds)
    throw "Timed out: $Description"
}

function Mark-Qa([string]$Description) {
    $notes.Add($Description)
    Write-Host "PASS: $Description"
}

function Find-Ui([string]$ControlId) {
    if (!$app -or $app.HasExited) { return }
    foreach ($handle in [CaseProofQaWindow]::VisibleWindows($app.Id)) {
        try {
            $window = [Windows.Automation.AutomationElement]::FromHandle($handle)
            $contains = [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::AutomationIdProperty, $ControlId)
            $element = $window.FindFirst([Windows.Automation.TreeScope]::Descendants, $contains)
            if ($element -and $element.Current.ProcessId -eq $app.Id) { return $element }
        } catch [Windows.Automation.ElementNotAvailableException] {}
    }
}

function Read-Ui([string]$ControlId) {
    $element = Find-Ui $ControlId
    if (!$element) { return }
    $pattern = $null
    if ($element.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
        return $pattern.Current.Value
    }
    return $element.Current.Name
}

function Invoke-Ui([string]$ControlId) {
    $element = Wait-Qa "enabled UI Automation control $ControlId" {
        $candidate = Find-Ui $ControlId
        if ($candidate -and $candidate.Current.IsEnabled -and !$candidate.Current.IsOffscreen) { $candidate }
    }
    ([Windows.Automation.InvokePattern]$element.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern)).Invoke()
}

function Select-Ui([Windows.Automation.AutomationElement]$Element) {
    ([Windows.Automation.SelectionItemPattern]$Element.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)).Select()
}

function Set-Ui([string]$ControlId, [string]$Value) {
    $element = Wait-Qa "visible UI Automation edit $ControlId" {
        $candidate = Find-Ui $ControlId
        if ($candidate -and !$candidate.Current.IsOffscreen) { $candidate }
    }
    $pattern = $null
    if ($element.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern, [ref]$pattern) -and !$pattern.Current.IsReadOnly) {
        try { $pattern.SetValue($Value); return } catch [System.Runtime.InteropServices.COMException] { }
    }
    if ($ControlId -ne 'TokenInput' -or $Value -notmatch '^[0-9a-f]+$') { throw "No writable edit pattern for $ControlId." }
    Assert-Qa ([CaseProofQaWindow]::Activate($mainWindow, $app.Id)) 'Could not foreground the owned test window.'
    $element.SetFocus()
    Assert-Qa ([CaseProofQaWindow]::Owned([CaseProofQaWindow]::GetForegroundWindow(), $app.Id)) 'Refusing typing in unrelated window.'
    [Windows.Forms.SendKeys]::SendWait($Value)
}

function Activate-Case([string]$Title) {
    $list = Find-Ui 'QueueList'
    if (!$list -or $list.Current.IsOffscreen) {
        Assert-Qa ([CaseProofQaWindow]::Activate($mainWindow, $app.Id)) 'Could not focus the owned queue test window.'
        Assert-Qa ([CaseProofQaWindow]::Owned([CaseProofQaWindow]::GetForegroundWindow(), $app.Id)) 'Refusing shortcut in unrelated window.'
        [Windows.Forms.SendKeys]::SendWait('^f')
        Wait-Qa 'Ctrl+F focus in the newly open request list' {
            $focused = [Windows.Automation.AutomationElement]::FocusedElement
            $focused.Current.ProcessId -eq $app.Id -and $focused.Current.AutomationId -eq 'SearchInput'
        } | Out-Null
        Mark-Qa 'Ctrl+F reopened the collapsed native queue and focused search.'
    }
    $item = Wait-Qa "queue row $Title" {
        $list = Find-Ui 'QueueList'
        if (!$list -or $list.Current.IsOffscreen) { return }
        $filter = [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty, [Windows.Automation.ControlType]::ListItem)
        $name = [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty, $Title)
        foreach ($candidate in $list.FindAll([Windows.Automation.TreeScope]::Descendants, $filter)) {
            if ($candidate.Current.Name.Contains($Title) -or $candidate.FindFirst([Windows.Automation.TreeScope]::Descendants, $name)) { $candidate; break }
        }
    }
    Select-Ui $item
    Wait-Qa "detail for $Title" { (Read-Ui 'ChangeTitle') -eq $Title } | Out-Null
}

function Start-Desktop {
    $script:app = Start-Process -FilePath $desktop -WorkingDirectory (Split-Path $desktop -Parent) -WindowStyle Normal -PassThru
    $script:mainWindow = Wait-Qa 'CaseProof main window' {
        $app.Refresh()
        if ($app.HasExited) { throw 'The CaseProof Windows process exited during startup.' }
        if ([CaseProofQaWindow]::Owned($app.MainWindowHandle, $app.Id)) { $app.MainWindowHandle }
    } 30
    $screen = [Windows.Forms.Screen]::FromHandle($mainWindow).WorkingArea
    $x = $screen.Left + 8
    $y = $screen.Top + 8
    $width = [Math]::Min(1440, $screen.Width - 16)
    $height = [Math]::Min(900, $screen.Height - 16)
    Assert-Qa ([CaseProofQaWindow]::SetWindowPos($mainWindow, [IntPtr]::Zero, $x, $y, $width, $height, 0x14)) 'Could not size the test window.'
}

function Stop-Desktop {
    if (!$app -or $app.HasExited) { return }
    $app.CloseMainWindow() | Out-Null
    if (!$app.WaitForExit(3000)) { $app.Kill(); $app.WaitForExit() }
}

function Login-Role([string]$Role) {
    if (Find-Ui 'SwitchRoleButton') {
        $roleButton = Find-Ui 'SwitchRoleButton'
        if (!$roleButton.Current.IsOffscreen) { Invoke-Ui 'SwitchRoleButton' }
    }
    Set-Ui 'EndpointInput' $fixture.url
    Set-Ui 'TokenInput' $fixture.tokens.$Role
    Invoke-Ui 'LoginButton'
    Wait-Qa "login of synthetic role $Role" { (Read-Ui 'ActorText') -match [regex]::Escape($Role) } 25 | Out-Null
}

function Capture-Desktop([string]$Filename) {
    Assert-Qa ([CaseProofQaWindow]::Owned($mainWindow, $app.Id)) 'Refusing to capture an unrelated process.'
    $rect = [CaseProofQaWindow+Rect]::new()
    Assert-Qa ([CaseProofQaWindow]::GetWindowRect($mainWindow, [ref]$rect)) 'Cannot read window dimensions.'
    $windowWidth = $rect.Right - $rect.Left
    $windowHeight = $rect.Bottom - $rect.Top
    $image = [Drawing.Bitmap]::new($windowWidth, $windowHeight)
    $frame = [CaseProofQaWindow+Rect]::new()
    try {
        $graphics = [Drawing.Graphics]::FromImage($image)
        try {
            $handle = $graphics.GetHdc()
            try { $printed = [CaseProofQaWindow]::PrintWindow($mainWindow, $handle, 2) } finally { $graphics.ReleaseHdc($handle) }
        } finally { $graphics.Dispose() }
        Assert-Qa $printed "PrintWindow failed for $Filename."
        $unique = [Collections.Generic.HashSet[int]]::new()
        for ($col = 16; $col -lt $windowWidth; $col += 19) {
            for ($row = 16; $row -lt $windowHeight; $row += 17) { $null = $unique.Add($image.GetPixel($col, $row).ToArgb()) }
        }
        Assert-Qa ($unique.Count -gt 7) "PrintWindow yielded a blank capture for $Filename."
        $width = $windowWidth
        $height = $windowHeight
        if ([CaseProofQaWindow]::GetVisibleFrame($mainWindow, [ref]$frame) -and
            $frame.Left -ge $rect.Left -and $frame.Right -le $rect.Right -and
            $frame.Top -ge $rect.Top -and $frame.Bottom -le $rect.Bottom) {
            $width = $frame.Right - $frame.Left
            $height = $frame.Bottom - $frame.Top
            $visible = [Drawing.Rectangle]::new($frame.Left - $rect.Left, $frame.Top - $rect.Top, $width, $height)
            $cropped = $image.Clone($visible, $image.PixelFormat)
            try { $cropped.Save((Join-Path $output $Filename), [Drawing.Imaging.ImageFormat]::Png) } finally { $cropped.Dispose() }
        } else { $image.Save((Join-Path $output $Filename), [Drawing.Imaging.ImageFormat]::Png) }
    } finally { $image.Dispose() }
    $captures.Add([ordered]@{ file = $Filename; width_pixels = $width; height_pixels = $height; window_width_pixels = $windowWidth;
                              window_height_pixels = $windowHeight; dpi = [CaseProofQaWindow]::GetDpiForWindow($mainWindow) })
}

function Api-Qa([string]$Method, [string]$Path, [string]$Role, $Payload = $null, [int]$Revision = 0) {
    $request = @{ Uri = $fixture.url + '/api/v1' + $Path; Method = $Method; TimeoutSec = 8
        Headers = @{ Authorization = 'Bearer ' + $fixture.tokens.$Role } }
    if ($Method -eq 'Post') {
        $request.Headers['Idempotency-Key'] = 'desktop_qa_' + [guid]::NewGuid().ToString('N')
        if ($Revision) { $request.Headers['X-Expected-Revision'] = [string]$Revision }
        $request.ContentType = 'application/json; charset=utf-8'
        $request.Body = [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $Payload -Depth 18 -Compress))
    }
    return (Invoke-RestMethod @request).data
}

function Confirm-NativeDecision([string]$Reason) {
    Invoke-Ui 'ApproveButton'
    Set-Ui 'DecisionReasonInput' $Reason
    Invoke-Ui 'DecisionConfirmButton'
}

function Test-StoredComparison {
    $title = '합성 보관 평가 비교 · 기준 불일치와 개정 통과'
    $request = $preset.create_body | ConvertTo-Json -Depth 18 | ConvertFrom-Json -AsHashtable
    $request.title = $title
    $created = Api-Qa Post '/changes' analyst $request
    $edited = @(ConvertTo-Json -InputObject $preset.case_inputs -Depth 18 | ConvertFrom-Json -AsHashtable)
    $edited[0].claim_days++
    $path = "/changes/$($created.change_id)/evaluation-runs"
    $blocked = Api-Qa Post $path analyst @{ suite_version_id = $created.suite_version_id; case_inputs = $edited } 1
    $passed = Api-Qa Post $path analyst @{ suite_version_id = $created.suite_version_id; case_inputs = @($preset.case_inputs) } 2
    Assert-Qa ($blocked.run.gate_summary -eq 'BLOCK' -and $passed.run.gate_summary -eq 'PASS') 'Expected two real stored runs with different outcomes.'
    Invoke-Ui 'RefreshButton'
    Activate-Case $title
    Select-Ui (Wait-Qa 'saved evaluation history tab' { Find-Ui 'HistoryTab' })
    Invoke-Ui 'CompareRunsButton'
    Invoke-Ui 'CompareRunsConfirmButton'
    Wait-Qa 'stored evaluation comparison with verdict transition' {
        $proof = Read-Ui 'ProofContent'
        (Read-Ui 'ProofTitle') -eq '저장 평가 비교' -and $proof -match '실패\s*→\s*통과' -and
            $proof.Contains($blocked.run.id) -and $proof.Contains($passed.run.id)
    } | Out-Null
    Capture-Desktop '06-native-stored-run-comparison.png'
    Mark-Qa 'Native stored-run comparison displays both retained run IDs and the real FAIL to PASS transition.'
}

try {
    $backendLog = Join-Path $practice 'backend.log'
    $backendErrors = Join-Path $practice 'backend-errors.log'
    $service = Start-Process -FilePath $python -WorkingDirectory $root `
        -ArgumentList @('-u', '-m', 'scripts.windows_checks', 'desktop.qa.fixture', ('"' + $practice + '"')) `
        -WindowStyle Hidden -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrors -PassThru
    $fixture = Wait-Qa 'disposable loopback API' {
        if ($service.HasExited) { throw "The synthetic API process exited. See $backendErrors" }
        $profile = Join-Path $practice 'fixture.json'
        if (!(Test-Path -LiteralPath $profile)) { return }
        $config = Get-Content -LiteralPath $profile -Raw | ConvertFrom-Json
        try { if ((Invoke-WebRequest -Uri ($config.url + '/v1') -TimeoutSec 2).StatusCode -eq 200) { $config } } catch [System.Net.Http.HttpRequestException] {}
    } 30
    $catalog = Api-Qa Get '/workspace' analyst
    $preset = $catalog.presets | Where-Object pack_id -eq 'lantern'
    foreach ($label in @('합성 참고 요청 · 시행일 확인', '합성 참고 요청 · 출처 점검')) {
        $body = $preset.create_body | ConvertTo-Json -Depth 18 | ConvertFrom-Json -AsHashtable
        $body.title = $label
        $null = Api-Qa Post '/changes' analyst $body
    }

    Start-Desktop
    Login-Role 'analyst'
    Invoke-Ui 'NewChangeButton'
    Set-Ui 'NewChangeTitleInput' $approvedTitle
    Invoke-Ui 'NewChangeConfirmButton'
    Wait-Qa 'native-created request' { (Read-Ui 'ChangeTitle') -eq $approvedTitle } | Out-Null
    $changeId = (Api-Qa Get '/changes' analyst | Where-Object title -eq $approvedTitle).change_id
    Assert-Qa ([bool]$changeId) 'The new Windows request did not reach the real API.'
    Invoke-Ui 'EvaluateButton'
    $evaluation = Wait-Qa 'evaluation UI or committed evaluation' {
        $evaluationDialog = Find-Ui 'EvaluationConfirmButton'
        if ($evaluationDialog -and !$evaluationDialog.Current.IsOffscreen) { 'dialog' }
        elseif ((Api-Qa Get "/changes/$changeId" analyst).snapshot.revision -eq 2) { 'recorded' }
    }
    if ($evaluation -eq 'dialog') { Invoke-Ui 'EvaluationConfirmButton' }
    Wait-Qa 'persisted PASS evaluation' { (Api-Qa Get "/changes/$changeId" analyst).latest_run.gate_summary -eq 'PASS' } | Out-Null
    Invoke-Ui 'SubmitButton'
    Wait-Qa 'persisted independent review queue' { (Api-Qa Get "/changes/$changeId" analyst).snapshot.status -eq 'PENDING_DOMAIN_REVIEW' } | Out-Null
    Mark-Qa 'Native analyst created, evaluated, and submitted a synthetic change to SQLite through the API.'

    Login-Role 'reviewer'
    Activate-Case $approvedTitle
    $proofButton = Find-Ui 'EvidenceButton'
    if (!$proofButton -or $proofButton.Current.IsOffscreen) { Invoke-Ui 'ToggleProofButton' }
    Invoke-Ui 'EvidenceButton'
    Wait-Qa 'rendered evidence inspector' {
        $element = Find-Ui 'ProofContent'
        $element -and !$element.Current.IsOffscreen -and (Read-Ui 'ProofContent') -match '현재 평가 실행' -and
            (Read-Ui 'ProofStatus') -match '기록.+현재 출처'
    } | Out-Null
    Capture-Desktop '01-native-domain-review.png'
    Select-Ui (Wait-Qa 'evaluation tab' { Find-Ui 'EvaluationTab' })
    $case = Wait-Qa 'actual case row for the selected evaluation' {
        $grid = Find-Ui 'EvaluationGrid'
        if (!$grid -or $grid.Current.IsOffscreen) { return }
        $kind = [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty, [Windows.Automation.ControlType]::DataItem)
        $grid.FindFirst([Windows.Automation.TreeScope]::Descendants, $kind)
    }
    Select-Ui $case
    Wait-Qa 'actual case provenance' {
        (Read-Ui 'ProofTitle') -eq '평가 사례 근거' -and (Read-Ui 'ProofContent') -match '관측 기준.+|적용 규칙'
    } | Out-Null
    Capture-Desktop '05-native-case-evidence.png'
    Mark-Qa 'Native evaluation row opened the retained case, observation date, and rule provenance.'
    Select-Ui (Wait-Qa 'comparison tab' { Find-Ui 'ComparisonTab' })
    Invoke-Ui 'ToggleQueueButton'
    Wait-Qa 'queue collapsed without clearing the selected request' {
        $list = Find-Ui 'QueueList'; (!$list -or $list.Current.IsOffscreen) -and (Read-Ui 'ChangeTitle') -eq $approvedTitle
    } | Out-Null
    Invoke-Ui 'ToggleQueueButton'
    Wait-Qa 'queue reopened without clearing the selected request' {
        $list = Find-Ui 'QueueList'; $list -and !$list.Current.IsOffscreen -and (Read-Ui 'ChangeTitle') -eq $approvedTitle
    } | Out-Null
    Mark-Qa 'Native queue collapsed and reopened with selected change retained.'
    $screen = [Windows.Forms.Screen]::FromHandle($mainWindow).WorkingArea
    Assert-Qa ([CaseProofQaWindow]::SetWindowPos($mainWindow, [IntPtr]::Zero, $screen.Left + 8, $screen.Top + 8, 1040, [Math]::Min(820, $screen.Height - 16), 0x14)) 'Could not exercise the narrow window.'
    Wait-Qa 'visible action in the narrow review window' { $control = Find-Ui 'ApproveButton'; $control -and !$control.Current.IsOffscreen } | Out-Null
    Capture-Desktop '02-native-narrow-review.png'
    Confirm-NativeDecision '합성 현업 검토에서 평가 사례와 출처를 확인했습니다.'
    Wait-Qa 'persisted independent final approval queue' { (Api-Qa Get "/changes/$changeId" reviewer).snapshot.status -eq 'PENDING_RELEASE' } | Out-Null
    Mark-Qa 'A separate native domain reviewer approved the same change.'

    Login-Role 'approver'
    Activate-Case $approvedTitle
    New-Item -ItemType File -Path (Join-Path $practice 'drop-next-release') | Out-Null
    Confirm-NativeDecision '합성 최종 승인에서 고정된 근거와 현업 검토를 확인했습니다.'
    Wait-Qa 'native final decision pending recovery' {
        $button = Find-Ui 'RecoveryButton'; $button -and $button.Current.IsEnabled -and !$button.Current.IsOffscreen
    } | Out-Null
    $committed = Api-Qa Get "/changes/$changeId" approver
    Assert-Qa ($committed.snapshot.status -eq 'APPROVED_FOR_DEMO') 'The server did not commit the decision before response loss.'
    $pendingFiles = @(Get-ChildItem -LiteralPath $env:CASEPROOF_DESKTOP_STATE_DIR -Filter '*.bin' -File)
    Assert-Qa ($pendingFiles.Count -eq 1) 'Expected exactly one protected pending decision on disk.'
    $storedText = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($pendingFiles[0].FullName))
    foreach ($syntheticToken in $fixture.tokens.PSObject.Properties.Value) {
        Assert-Qa (!$storedText.Contains($syntheticToken)) 'Synthetic bearer token was written to pending storage.'
    }
    Capture-Desktop '03-native-reply-lost.png'
    Stop-Desktop
    Start-Desktop
    Login-Role 'reviewer'
    $otherRoleRecovery = Find-Ui 'RecoveryButton'
    Assert-Qa (!$otherRoleRecovery -or $otherRoleRecovery.Current.IsOffscreen) 'Another role can see the pending request.'
    Mark-Qa 'Pending native recovery persists without a bearer token and is hidden from a different role after restart.'
    Login-Role 'approver'
    Invoke-Ui 'RecoveryButton'
    Wait-Qa 'same authorized decision resolved after Windows restart' {
        $control = Find-Ui 'RecoveryButton'
        (!$control -or !$control.Current.IsEnabled -or $control.Current.IsOffscreen) -and (Read-Ui 'StatusText') -match '원래 요청'
    } | Out-Null
    $requests = Get-Content -LiteralPath (Join-Path $practice 'http-events.jsonl') | ForEach-Object { $_ | ConvertFrom-Json }
    $writes = @($requests | Where-Object { $_.method -eq 'POST' -and $_.path -eq "/api/v1/changes/$changeId/release-decision" })
    Assert-Qa ($writes.Count -eq 1 -and $writes[0].dropped -and $writes[0].status -eq 200) 'Expected exactly one committed final-decision POST.'
    $replay = @($requests | Where-Object { $_.method -eq 'GET' -and $_.path -eq '/api/v1/mutations/{key}' -and $_.key_sha256 -eq $writes[0].key_sha256 })
    Assert-Qa ($replay.Count -eq 1 -and $replay[0].status -eq 200) 'Native recovery did not use the same accepted idempotency key and one authorized GET.'
    $evidence = Api-Qa Get "/changes/$changeId/evidence" approver
    Assert-Qa ($evidence.approved_revision -eq 5 -and $evidence.historical_integrity -eq 'VALID' -and [bool]$evidence.envelope_sha256) 'The original approval evidence or revision is missing.'
    Capture-Desktop '04-native-recovered-approval.png'
    Mark-Qa 'Native final approval committed before controlled reply loss and recovered after app restart by one GET with the original key, without reposting.'
    if ($CompareStoredRuns) {
        try { Test-StoredComparison } catch {
            $comparisonError = $_.Exception.Message
            Write-Host "FAIL (separate saved evaluation comparison): $comparisonError"
        }
    }
} catch {
    Write-Host "FAIL: $($_.Exception.Message)"
    Write-Host "Private throwaway logs: $practice"
    throw
} finally {
    try {
        [ordered]@{ checks = $notes; captures = $captures; comparison_error = $comparisonError } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'native-qa.json') -Encoding utf8
        Stop-Desktop
    } finally {
        if ($service -and !$service.HasExited) {
            New-Item -ItemType File -Path (Join-Path $practice 'stop-fixture') -Force | Out-Null
            if (!$service.WaitForExit(8000)) { $service.Kill($true); $service.WaitForExit() }
        }
        $env:CASEPROOF_DESKTOP_STATE_DIR = $priorAppState
        if ($priorDpi -ne [IntPtr]::Zero) { $null = [CaseProofQaWindow]::SetThreadDpiAwarenessContext($priorDpi) }
    }
}
