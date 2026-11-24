param(
    [Parameter(Mandatory)][string]$DesktopExe,
    [Parameter(Mandatory)][string]$PythonExe,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [switch]$CompareStoredRuns,
    [switch]$VerifyRedesign,
    [switch]$AssertCaseControlsOnly
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
$nativeFrame = $null
$narrowActionBounds = $null
$wideWorkflowBounds = $null
$inlineEvidenceBounds = $null
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
    [DllImport("user32.dll", EntryPoint = "GetWindowLongW")] public static extern int GetWindowStyle(IntPtr hwnd, int index);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr dc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hwnd, IntPtr insertAfter, int x, int y, int width, int height, uint flags);
    [DllImport("dwmapi.dll")] private static extern int DwmGetWindowAttribute(IntPtr hwnd, int attr, out Rect rect, int size);
    [DllImport("dwmapi.dll", EntryPoint = "DwmGetWindowAttribute")] private static extern int DwmGetColorAttribute(IntPtr hwnd, int attr, out uint color, int size);

    public static string GetColor(IntPtr hwnd, int attr) {
        uint value;
        if (DwmGetColorAttribute(hwnd, attr, out value, 4) != 0 || value > 0xFFFFFF) return null;
        return String.Format("#{0:X2}{1:X2}{2:X2}", value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF);
    }

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

function Refresh-Workbench {
    Invoke-Ui 'RefreshButton'
    Wait-Qa 'desktop finished refreshing its request queue' {
        $button = Find-Ui 'RefreshButton'
        $button -and $button.Current.IsEnabled -and (Read-Ui 'StatusText') -eq '최신 요청 목록을 확인했습니다.'
    } | Out-Null
}

function Select-Ui([Windows.Automation.AutomationElement]$Element) {
    ([Windows.Automation.SelectionItemPattern]$Element.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)).Select()
}

function Test-VisibleUi([string]$ControlId) {
    $element = Find-Ui $ControlId
    return $element -and !$element.Current.IsOffscreen
}

function Select-CaseFilter([string]$FilterId) {
    $filter = Wait-Qa 'visible case filter control' {
        $element = Find-Ui 'CaseFilterInput'
        if ($element -and !$element.Current.IsOffscreen) { $element }
    }
    $toggle = [Windows.Automation.ExpandCollapsePattern]$filter.GetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern)
    $toggle.Expand()
    $item = Wait-Qa "case filter item $FilterId" {
        $condition = [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::AutomationIdProperty, $FilterId)
        $candidate = $filter.FindFirst([Windows.Automation.TreeScope]::Descendants, $condition)
        if ($candidate) { $candidate } else { Find-Ui $FilterId }
    }
    Select-Ui $item
    $toggle.Collapse()
}

function Get-DataGridRows([string]$GridId) {
    $grid = Find-Ui $GridId
    if (!$grid -or $grid.Current.IsOffscreen) { return }
    $condition = [Windows.Automation.PropertyCondition]::new(
        [Windows.Automation.AutomationElement]::ControlTypeProperty, [Windows.Automation.ControlType]::DataItem)
    foreach ($row in $grid.FindAll([Windows.Automation.TreeScope]::Children, $condition)) { $row }
}

function Get-DataRowText([Windows.Automation.AutomationElement]$Row) {
    $cells = @($Row.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition))
    return (@($Row.Current.Name) + @($cells | ForEach-Object {
        $value = $null
        if ($_.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern, [ref]$value)) { $value.Current.Value }
        $_.Current.Name
    })) -join ' '
}

function Select-EvaluationCase([string]$CaseId) {
    $row = Wait-Qa "stored case $CaseId in evaluation grid" {
        Get-DataGridRows 'EvaluationGrid' | Where-Object { (Get-DataRowText $_).Contains($CaseId) } | Select-Object -First 1
    }
    Select-Ui $row
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
        if (!$list -or $list.Current.IsOffscreen -or !$list.Current.IsEnabled) { return }
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

function Capture-Desktop([string]$Filename, [IntPtr]$WindowHandle = $mainWindow) {
    Assert-Qa ([CaseProofQaWindow]::Owned($WindowHandle, $app.Id)) 'Refusing to capture an unrelated process.'
    $rect = [CaseProofQaWindow+Rect]::new()
    Assert-Qa ([CaseProofQaWindow]::GetWindowRect($WindowHandle, [ref]$rect)) 'Cannot read window dimensions.'
    $windowWidth = $rect.Right - $rect.Left
    $windowHeight = $rect.Bottom - $rect.Top
    $image = [Drawing.Bitmap]::new($windowWidth, $windowHeight)
    $frame = [CaseProofQaWindow+Rect]::new()
    try {
        $graphics = [Drawing.Graphics]::FromImage($image)
        try {
            $handle = $graphics.GetHdc()
            try { $printed = [CaseProofQaWindow]::PrintWindow($WindowHandle, $handle, 2) } finally { $graphics.ReleaseHdc($handle) }
        } finally { $graphics.Dispose() }
        Assert-Qa $printed "PrintWindow failed for $Filename."
        $unique = [Collections.Generic.HashSet[int]]::new()
        for ($col = 16; $col -lt $windowWidth; $col += 19) {
            for ($row = 16; $row -lt $windowHeight; $row += 17) { $null = $unique.Add($image.GetPixel($col, $row).ToArgb()) }
        }
        Assert-Qa ($unique.Count -gt 7) "PrintWindow yielded a blank capture for $Filename."
        $width = $windowWidth
        $height = $windowHeight
        if ([CaseProofQaWindow]::GetVisibleFrame($WindowHandle, [ref]$frame) -and
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
                              window_height_pixels = $windowHeight; dpi = [CaseProofQaWindow]::GetDpiForWindow($WindowHandle) })
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

function Confirm-NativeDecision([string]$Reason, [string]$ExpectedClause = '') {
    Invoke-Ui 'ApproveButton'
    if ($ExpectedClause) {
        Wait-Qa 'decision dialog includes the current case and clause version' {
            $context = Read-Ui 'DecisionContext'
            (Test-VisibleUi 'DecisionContext') -and (Test-VisibleUi 'DecisionReasonInput') -and
                $context -and $context.Contains($ExpectedClause) -and $context -match 'v1'
        } | Out-Null
        $dialog = Wait-Qa 'native decision dialog window' {
            $condition = [Windows.Automation.PropertyCondition]::new(
                [Windows.Automation.AutomationElement]::AutomationIdProperty, 'DecisionContext')
            foreach ($handle in [CaseProofQaWindow]::VisibleWindows($app.Id)) {
                if ($handle -eq $mainWindow) { continue }
                $window = [Windows.Automation.AutomationElement]::FromHandle($handle)
                if ($window.FindFirst([Windows.Automation.TreeScope]::Descendants, $condition)) { $handle; break }
            }
        }
        Capture-Desktop '10-native-decision-evidence.png' $dialog
        Mark-Qa 'The decision dialog includes the selected stored case clause and version alongside the reason.'
        if (![Windows.Forms.SystemInformation]::HighContrast) {
            $frame = [CaseProofQaWindow+Rect]::new()
            Assert-Qa ([CaseProofQaWindow]::GetVisibleFrame($dialog, [ref]$frame)) 'Could not measure the decision dialog frame.'
            $bounds = (Find-Ui 'DecisionReasonInput').Current.BoundingRectangle
            $scale = [CaseProofQaWindow]::GetDpiForWindow($dialog) / 96
            $left = [int]($bounds.Left - $frame.Left)
            $top = [int]($bounds.Top - $frame.Top - 24 * $scale)
            $bottom = [int]($bounds.Top - $frame.Top - 4 * $scale)
            $bright = 0
            $image = [Drawing.Bitmap]::new((Join-Path $output '10-native-decision-evidence.png'))
            try {
                for ($y = [Math]::Max(0, $top); $y -lt [Math]::Min($image.Height, $bottom); $y++) {
                    for ($x = [Math]::Max(0, $left); $x -lt [Math]::Min($image.Width, $left + 170 * $scale); $x++) {
                        $pixel = $image.GetPixel($x, $y)
                        if ($pixel.R -gt 145 -and $pixel.G -gt 145 -and $pixel.B -gt 145) { $bright++ }
                    }
                }
            } finally { $image.Dispose() }
            Assert-Qa ($bright -ge 40) 'The native reason label is not visibly contrasted against its dark background.'
            Mark-Qa 'The native reason label remains visibly contrasted in the rendered dark confirmation window.'
        }
    }
    Set-Ui 'DecisionReasonInput' $Reason
    Invoke-Ui 'DecisionConfirmButton'
}

function Open-AuditDisclosure([string]$Description) {
    $audit = Wait-Qa $Description {
        $control = Find-Ui 'ProofAuditExpander'
        if ($control -and !$control.Current.IsOffscreen) { $control }
    }
    $toggle = [Windows.Automation.ExpandCollapsePattern]$audit.GetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern)
    Assert-Qa ($toggle.Current.ExpandCollapseState -eq [Windows.Automation.ExpandCollapseState]::Collapsed) 'Audit references must start collapsed.'
    $toggle.Expand()
    return $toggle
}

function Close-AuditDisclosure([Windows.Automation.ExpandCollapsePattern]$Toggle) {
    $Toggle.Collapse()
    Wait-Qa 'audit references folded again' {
        $Toggle.Current.ExpandCollapseState -eq [Windows.Automation.ExpandCollapseState]::Collapsed
    } | Out-Null
}

function Test-RedesignedInspector([string]$ChangeId) {
    $visibleProof = Read-Ui 'ProofContent'
    Assert-Qa ([bool]$visibleProof -and $visibleProof -notmatch '(?i)\b[0-9a-f]{64}\b') 'Opening a case puts raw SHA-256 hashes in the default proof text.'
    $cases = @((Api-Qa Get "/changes/$ChangeId" reviewer).latest_run.case_results)
    $caseResult = $cases[0]
    Assert-Qa ($caseResult.input_sha256 -match '^[0-9a-f]{64}$' -and $caseResult.output_sha256 -match '^[0-9a-f]{64}$') 'The real selected evaluation case is missing its input/output references.'
    $passed = @($cases | Where-Object verdict -eq 'PASS').Count
    $failed = @($cases | Where-Object verdict -eq 'FAIL').Count
    Assert-Qa ((Read-Ui 'ReviewSignal') -match "검증 $($cases.Count)건.+통과 $passed.+실패 $failed") 'The review signal does not match the stored evaluation case counts.'
    $meta = Read-Ui 'ChangeMeta'
    Assert-Qa ($meta.Contains($ChangeId.Substring(0, 8)) -and !$meta.Contains($ChangeId)) 'The workbench header should show a short request reference.'
    $toggle = Open-AuditDisclosure 'visible audit references disclosure'
    Wait-Qa 'audit references match the stored run' {
        $evidence = Read-Ui 'ProofAuditContent'
        $evidence -and $evidence.Contains($caseResult.input_sha256) -and $evidence.Contains($caseResult.output_sha256)
    } | Out-Null
    Capture-Desktop '07-native-audit-disclosure.png'
    Close-AuditDisclosure $toggle
    Assert-Qa ((Read-Ui 'ChangeTitle') -eq $approvedTitle) 'The audit disclosure lost the selected request.'
    Mark-Qa 'The case proof shows basis and outcome first. The collapsed audit disclosure retains the exact input and output SHA-256 references.'
}

function Test-RecordedApprovalAudit($Evidence) {
    $summary = Wait-Qa 'recovered approval summary' {
        $proof = Read-Ui 'ProofContent'
        if ((Read-Ui 'ProofTitle') -eq '결정 당시 근거' -and $proof -match "승인 당시 개정\s+$($Evidence.approved_revision)") { $proof }
    }
    Assert-Qa (!$summary.Contains($Evidence.envelope_sha256)) 'The approval digest should be inside the audit disclosure.'
    $toggle = Open-AuditDisclosure 'audit references for the recovered approval'
    Wait-Qa 'the exact recovered approval digest' {
        $proof = Read-Ui 'ProofAuditContent'
        $proof -and $proof.Contains($Evidence.envelope_sha256)
    } | Out-Null
    Close-AuditDisclosure $toggle
    Mark-Qa 'The recovered approval provides the retained revision in the default proof and the exact approval digest in the audit disclosure.'
}

function Test-NativeCaption {
    $style = [CaseProofQaWindow]::GetWindowStyle($mainWindow, -16)
    $mask = 0x00CF0000
    Assert-Qa (($style -band $mask) -eq $mask) 'The main window does not retain the Windows caption, system menu, resize frame, and min/max buttons.'
    $image = [Drawing.Bitmap]::new((Join-Path $output '01-native-domain-review.png'))
    try {
        $sampleY = [Math]::Round(11 * [CaseProofQaWindow]::GetDpiForWindow($mainWindow) / 96)
        $pixels = @(foreach ($ratio in @(0.37, 0.50, 0.63)) {
            $pixel = $image.GetPixel([int]($image.Width * $ratio), [int]$sampleY)
            '#{0:X2}{1:X2}{2:X2}' -f $pixel.R, $pixel.G, $pixel.B
        })
    } finally { $image.Dispose() }
    $caption = [CaseProofQaWindow]::GetColor($mainWindow, 35)
    $captionText = [CaseProofQaWindow]::GetColor($mainWindow, 36)
    $border = [CaseProofQaWindow]::GetColor($mainWindow, 34)
    if ([Environment]::OSVersion.Version.Build -ge 22000 -and ![Windows.Forms.SystemInformation]::HighContrast) {
        Assert-Qa (@($pixels | Where-Object { $_ -ne '#080808' }).Count -eq 0) "The rendered native caption did not use the CaseProof color (actual: $($pixels -join ', '))."
    }
    $script:nativeFrame = [ordered]@{ caption_style = ('0x{0:X8}' -f $style); rendered_caption_samples = $pixels;
        caption_color_readback = $caption; caption_text_color_readback = $captionText; border_color_readback = $border }
    Mark-Qa 'The real HWND retains Windows caption controls. Native caption pixels confirm the themed color.'
}

function Test-NarrowDecisionBounds {
    $frame = [CaseProofQaWindow+Rect]::new()
    Assert-Qa ([CaseProofQaWindow]::GetVisibleFrame($mainWindow, [ref]$frame)) 'Could not measure the DWM frame of the narrow window.'
    $action = Find-Ui 'ApproveButton'
    $bounds = $action.Current.BoundingRectangle
    Assert-Qa ($action.Current.IsEnabled -and !$action.Current.IsOffscreen -and $bounds.Width -gt 0 -and $bounds.Height -gt 0 -and
        $bounds.Left -ge $frame.Left -and $bounds.Right -le $frame.Right -and $bounds.Top -ge $frame.Top -and $bounds.Bottom -le $frame.Bottom) 'The active decision control is clipped in the narrow review window.'
    $script:narrowActionBounds = [ordered]@{ x = $bounds.Left - $frame.Left; y = $bounds.Top - $frame.Top; width = $bounds.Width;
        height = $bounds.Height; frame_width = $frame.Right - $frame.Left; frame_height = $frame.Bottom - $frame.Top }
    Mark-Qa 'The whole enabled decision button fits inside the narrow visible window frame.'
}

function Test-WideWorkflowBounds {
    $frame = [CaseProofQaWindow+Rect]::new()
    Assert-Qa ([CaseProofQaWindow]::GetVisibleFrame($mainWindow, [ref]$frame)) 'Could not measure the wide DWM frame.'
    $rows = @(Get-DataGridRows 'EvaluationGrid')
    $case = $rows[0].Current.BoundingRectangle
    $queue = (Find-Ui 'QueueList').Current.BoundingRectangle
    $proof = (Find-Ui 'ProofContent').Current.BoundingRectangle
    $decision = (Find-Ui 'DecisionStatus').Current.BoundingRectangle
    $dpi = [CaseProofQaWindow]::GetDpiForWindow($mainWindow)
    $rowHeight = $case.Height * 96 / $dpi
    $firstY = ($case.Top - $frame.Top) * 96 / $dpi
    $script:wideWorkflowBounds = [ordered]@{
        dpi = $dpi
        frame_width = $frame.Right - $frame.Left
        frame_height = $frame.Bottom - $frame.Top
        first_case_y_dip = [Math]::Round($firstY, 1)
        first_case_height_dip = [Math]::Round($rowHeight, 1)
        decision_y = [Math]::Round($decision.Top - $frame.Top)
    }
    Assert-Qa ($queue.Width -gt 0 -and $proof.Width -gt 0 -and $case.Width -gt 0 -and
        $queue.Right -le $case.Left -and $case.Right -le $proof.Left) "The wide queue, evaluation rows, and evidence inspector bounds are not disjoint (queue $queue, case $case, proof $proof)."
    Assert-Qa ($firstY -le 210 -and $rowHeight -ge 30 -and $rowHeight -le 41 -and $decision.Top -gt $case.Bottom -and
        $decision.Bottom -le $frame.Bottom) "The first case or fixed rail falls outside its review region (first case Y $([Math]::Round($firstY, 1)) DIP, height $([Math]::Round($rowHeight, 1)) DIP, decision $decision)."
    if (![Windows.Forms.SystemInformation]::HighContrast) {
        $image = [Drawing.Bitmap]::new((Join-Path $output '08-native-mixed-outcomes-wide.png'))
        try {
            $plainRow = $rows[1].Current.BoundingRectangle
            $pixel = $image.GetPixel([int]($plainRow.Right - $frame.Left - 8), [int]($plainRow.Top - $frame.Top + 5))
        } finally { $image.Dispose() }
        $rowColor = '#{0:X2}{1:X2}{2:X2}' -f $pixel.R, $pixel.G, $pixel.B
        $script:wideWorkflowBounds.unselected_case_color = $rowColor
        Assert-Qa ($pixel.R -lt 64 -and $pixel.G -lt 64 -and $pixel.B -lt 64) "An unselected evaluation row lost its black theme (actual $rowColor)."
    }
    Mark-Qa 'The wide native view separates the queue, case grid, evidence panel, and fixed decision rail.'
}

function Test-MixedCaseNavigation($MixedPreset) {
    $title = '합성 제출 기한 검토 · 실패 1건과 미확정 1건'
    $request = $MixedPreset.create_body | ConvertTo-Json -Depth 18 | ConvertFrom-Json -AsHashtable
    $request.title = $title
    $created = Api-Qa Post '/changes' analyst $request
    $edited = @(ConvertTo-Json -InputObject $MixedPreset.case_inputs -Depth 18 | ConvertFrom-Json -AsHashtable)
    $edited[0].claim_days++
    $edited[1].case_context.incident_date = $null
    $run = (Api-Qa Post "/changes/$($created.change_id)/evaluation-runs" analyst @{
        suite_version_id = $created.suite_version_id
        case_inputs = $edited
    } 1).run
    Assert-Qa (@($run.case_results | Where-Object verdict -eq 'FAIL').Count -eq 1 -and
        @($run.case_results | Where-Object verdict -eq 'INCONCLUSIVE').Count -eq 1 -and
        @($run.case_results | Where-Object verdict -eq 'PASS').Count -eq 2) 'The mixed fixture does not contain its real stored outcomes.'
    Refresh-Workbench
    Activate-Case $title
    Select-Ui (Wait-Qa 'mixed evaluation tab' { Find-Ui 'EvaluationTab' })
    Wait-Qa 'all four stored cases rendered in the native grid' {
        @(Get-DataGridRows 'EvaluationGrid').Count -eq 4 -and [bool](Read-Ui 'CaseFilterSummary')
    } | Out-Null
    Select-EvaluationCase 'qa-1-window-failed'
    Wait-Qa 'failed case and actual L-1 coverage' {
        (Read-Ui 'ProofStatus') -match 'qa-1-window-failed' -and (Read-Ui 'ProofContent') -match 'L-1.+v1'
    } | Out-Null
    Capture-Desktop '08-native-mixed-outcomes-wide.png'
    Test-WideWorkflowBounds
    Select-CaseFilter 'CaseFilterAttention'
    Wait-Qa 'only two cases remain in attention filter' { @(Get-DataGridRows 'EvaluationGrid').Count -eq 2 } | Out-Null
    Select-EvaluationCase 'qa-1-window-failed'
    Invoke-Ui 'NextCaseButton'
    try {
        Wait-Qa 'native next-case navigation selected the inconclusive case' {
            (Read-Ui 'ProofStatus') -match 'qa-2-context-uncertain' -and (Read-Ui 'ProofContent') -match '조항\s*·\s*버전\s+미확정'
        } | Out-Null
    } catch {
        Capture-Desktop 'mixed-next-case-failure.png'
        Write-Host "Next-case proof status: $(Read-Ui 'ProofStatus')"
        Write-Host "Next-case proof: $(Read-Ui 'ProofContent')"
        foreach ($candidate in @(Get-DataGridRows 'EvaluationGrid')) {
            $selection = [Windows.Automation.SelectionItemPattern]$candidate.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)
            Write-Host "Selected $($selection.Current.IsSelected): $(Get-DataRowText $candidate)"
        }
        throw
    }
    Wait-Qa 'next-case navigation ends at the last attention case' {
        $control = Find-Ui 'NextCaseButton'
        $control -and !$control.Current.IsEnabled
    } | Out-Null
    Select-CaseFilter 'CaseFilterPass'
    Wait-Qa 'passing case filter cleared the excluded case proof' {
        $rows = @(Get-DataGridRows 'EvaluationGrid')
        $status = Read-Ui 'ProofStatus'
        $proof = Read-Ui 'ProofContent'
        $rows.Count -eq 2 -and $status -notmatch 'qa-[12]-' -and $proof -notmatch 'qa-[12]-'
    } | Out-Null
    $draft = Api-Qa Get "/changes/$($created.change_id)" analyst
    Assert-Qa ($draft.snapshot.revision -eq 2 -and $draft.snapshot.status -eq 'DRAFT' -and
        $draft.latest_run.id -eq $run.id) 'Moving between evidence cases changed the stored request.'
    Select-CaseFilter 'CaseFilterAll'
    Mark-Qa 'A real mixed evaluation can filter cases and advance to the next inconclusive result without retaining stale proof or writing a decision.'
}

function Test-NarrowInlineEvidence {
    $screen = [Windows.Forms.Screen]::FromHandle($mainWindow).WorkingArea
    $dpi = [CaseProofQaWindow]::GetDpiForWindow($mainWindow)
    $width = [Math]::Min(1040, [int][Math]::Floor(768 * $dpi / 96))
    Assert-Qa ([CaseProofQaWindow]::SetWindowPos($mainWindow, [IntPtr]::Zero, $screen.Left + 8, $screen.Top + 8, $width, [Math]::Min(820, $screen.Height - 16), 0x14)) 'Could not exercise the inline-proof width.'
    Select-Ui (Wait-Qa 'evaluation tab while narrow' { Find-Ui 'EvaluationTab' })
    Select-EvaluationCase 'harbor-base'
    $inline = Wait-Qa 'visible inline evidence below the selected case' {
        $element = Find-Ui 'InlineEvidenceText'
        $proof = Read-Ui 'InlineEvidenceText'
        if ($element -and !$element.Current.IsOffscreen -and $proof -match 'H-1.+v1') { $element }
    }
    $frame = [CaseProofQaWindow+Rect]::new()
    Assert-Qa ([CaseProofQaWindow]::GetVisibleFrame($mainWindow, [ref]$frame)) 'Could not measure the inline-proof frame.'
    $bounds = $inline.Current.BoundingRectangle
    $action = (Find-Ui 'ApproveButton').Current.BoundingRectangle
    Assert-Qa (!(Test-VisibleUi 'ProofContent') -and $bounds.Top -lt $action.Top -and $bounds.Left -ge $frame.Left -and
        $bounds.Right -le $frame.Right) 'Narrow evidence overlays the case grid, decision rail, or native frame.'
    $script:inlineEvidenceBounds = [ordered]@{
        window_width_dip = [Math]::Round(($frame.Right - $frame.Left) * 96 / $dpi, 1)
        width = $bounds.Width
        height = $bounds.Height
        y = $bounds.Top - $frame.Top
        action_y = $action.Top - $frame.Top
    }
    Capture-Desktop '09-native-inline-case-evidence.png'
    Mark-Qa 'At the native narrow breakpoint, the stored clause appears inside the selected case row and the decision remains visible.'
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
    Refresh-Workbench
    Activate-Case $title
    Select-Ui (Wait-Qa 'saved evaluation history tab' { Find-Ui 'HistoryTab' })
    Invoke-Ui 'CompareRunsButton'
    Invoke-Ui 'CompareRunsConfirmButton'
    if ($VerifyRedesign) {
        $shortLeft = $blocked.run.id.Substring(0, 8)
        $shortRight = $passed.run.id.Substring(0, 8)
        Wait-Qa 'comparison results in the main workbench rather than only the evidence inspector' {
            $summary = Read-Ui 'RunDiffSummary'
            $items = @(Get-DataGridRows 'RunDiffGrid')
            $summary -and $summary.Contains($shortLeft) -and $summary.Contains($shortRight) -and
                $items.Count -eq 1 -and (Get-DataRowText $items[0]) -match '실패.*통과'
        } | Out-Null
        $summary = Read-Ui 'RunDiffSummary'
        Assert-Qa (!$summary.Contains($blocked.run.id) -and !$summary.Contains($passed.run.id)) 'The default comparison contains full run IDs.'
        $toggle = Open-AuditDisclosure 'audit references for the stored comparison'
        Wait-Qa 'both exact retained comparison run IDs' {
            $evidence = Read-Ui 'ProofAuditContent'
            $evidence -and $evidence.Contains($blocked.run.id) -and $evidence.Contains($passed.run.id)
        } | Out-Null
        Close-AuditDisclosure $toggle
        Capture-Desktop '06-native-stored-run-comparison.png'
        Mark-Qa 'The main native comparison grid displays the real FAIL-to-PASS transition and audit retains both exact run IDs.'
        return
    }
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
    $preset = $catalog.presets | Where-Object id -eq 'lantern'
    foreach ($label in @('합성 참고 요청 · 시행일 확인', '합성 참고 요청 · 출처 점검')) {
        $body = $preset.create_body | ConvertTo-Json -Depth 18 | ConvertFrom-Json -AsHashtable
        $body.title = $label
        $null = Api-Qa Post '/changes' analyst $body
    }

    Start-Desktop
    Login-Role 'analyst'
    if ($AssertCaseControlsOnly) {
        Select-Ui (Wait-Qa 'evaluation tab' { Find-Ui 'EvaluationTab' })
        Assert-Qa ([bool](Find-Ui 'CaseFilterInput')) 'The native evaluation view does not expose its case filter.'
        Assert-Qa ([bool](Find-Ui 'NextCaseButton')) 'The native evaluation view does not expose next-case navigation.'
        Mark-Qa 'The evaluation view exposes case filtering and next-case navigation through UI Automation.'
        return
    }
    if ($VerifyRedesign) {
        Test-MixedCaseNavigation ($catalog.presets | Where-Object id -eq 'qa-review-cases')
    }
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
    Select-Ui (Wait-Qa 'execution comparison tab for the request overview' { Find-Ui 'ComparisonTab' })
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
    if ($VerifyRedesign) {
        Test-RedesignedInspector $changeId
        Test-NativeCaption
    }
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
    if ($VerifyRedesign) { Test-NarrowDecisionBounds }
    Capture-Desktop '02-native-narrow-review.png'
    if ($VerifyRedesign) {
        Test-NarrowInlineEvidence
        Confirm-NativeDecision '합성 현업 검토에서 평가 사례와 출처를 확인했습니다.' 'H-1'
    } else {
        Confirm-NativeDecision '합성 현업 검토에서 평가 사례와 출처를 확인했습니다.'
    }
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
    if ($VerifyRedesign) { Test-RecordedApprovalAudit $evidence }
    Capture-Desktop '04-native-recovered-approval.png'
    Mark-Qa 'Native final approval committed before controlled reply loss and recovered after app restart by one GET with the original key, without reposting.'
    if ($CompareStoredRuns) {
        try { Test-StoredComparison } catch {
            $comparisonError = $_.Exception.Message
            Write-Host "FAIL (separate saved evaluation comparison): $comparisonError"
            if ($VerifyRedesign) { throw }
        }
    }
} catch {
    Write-Host "FAIL: $($_.Exception.Message)"
    Write-Host "Private throwaway logs: $practice"
    throw
} finally {
    try {
        [ordered]@{ checks = $notes; captures = $captures; native_frame = $nativeFrame; wide_workflow_bounds = $wideWorkflowBounds;
            narrow_action_bounds = $narrowActionBounds; inline_evidence_bounds = $inlineEvidenceBounds; comparison_error = $comparisonError } |
            ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'native-qa.json') -Encoding utf8
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
