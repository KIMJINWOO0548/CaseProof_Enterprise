using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using Microsoft.Win32;

namespace CaseProof.Desktop;

public partial class MainWindow : Window
{
    private sealed record ChangeRow(string Id, string Title, string Status, string StatusCode, string Revision, string Pack);
    private sealed record ReviewField(string Item, string Value);
    private sealed record CaseRow(string Id, string Outcome, string Resolution, string Source, JsonElement Data);
    private sealed record HistoryRow(string Revision, string Action, string Actor, string Time, string Reason);
    private sealed record RunChoice(string Id, string Label);

    private readonly CancellationTokenSource closing = new();
    private WorkspaceClient? client;
    private List<ChangeRow> queue = [];
    private JsonElement selected;
    private JsonElement review;
    private JsonElement execution;
    private int generation;
    private bool updatingQueue;
    private bool busy;
    private bool reading;
    private bool queueOpen = true;
    private bool proofOpen;
    private double queueWidth = 250;
    private double proofWidth = 310;
    private string ChangeId => selected.Text("change_id");
    private int Revision => selected.Number("revision");
    private string Phase => selected.Text("status");
    private string RunId => execution.Text("id", review.Field("evaluation").Text("run_id"));
    private string ChangePath => $"/api/v1/changes/{ChangeId}";
    private bool HasSelection => ChangeId.Length != 0;

    public MainWindow()
    {
        InitializeComponent();
        var workArea = SystemParameters.WorkArea;
        Width = Math.Min(Width, Math.Max(MinWidth, workArea.Width));
        Height = Math.Min(Height, Math.Max(MinHeight, workArea.Height));
        foreach (var control in new FrameworkElement[] { EndpointInput, TokenInput, LoginButton, QueueList, ToggleQueueButton,
            ToggleProofButton, RefreshButton, NewChangeButton, SwitchRoleButton, RecoveryButton, SubmitButton, EvaluateButton,
            ApproveButton, RejectButton, EvidenceButton, ProofContent, ActorText, StatusText, ChangeTitle, EvaluationGrid,
            HistoryGrid, SearchInput, FilterInput, CompareRunsButton, PreviewCsvButton })
            AutomationProperties.SetAutomationId(control, control.Name);
        Loaded += (_, _) => { ApplyPaneLayout(); TokenInput.Focus(); };
        SizeChanged += (_, _) => ApplyPaneLayout();
        Closed += (_, _) => { closing.Cancel(); client?.Dispose(); };
        LoginButton.Click += async (_, _) => await ConnectAsync();
        TokenInput.KeyDown += async (_, key) =>
        {
            if (key.Key == Key.Enter && LoginButton.IsEnabled) { key.Handled = true; await ConnectAsync(); }
        };
        PreviewKeyDown += HandleShortcut;
        SwitchRoleButton.Click += (_, _) => SignOut("다른 역할의 토큰으로 연결하세요.");
        QueueList.SelectionChanged += async (_, _) =>
        {
            if (!updatingQueue && QueueList.SelectedItem is ChangeRow row && !busy)
                await LoadChangeAsync(row.Id);
        };
        SearchInput.TextChanged += (_, _) => FilterQueue();
        FilterInput.SelectionChanged += (_, _) => FilterQueue();
        ToggleQueueButton.Click += (_, _) => ToggleQueue();
        ToggleProofButton.Click += (_, _) => ToggleProof();
        RefreshButton.Click += async (_, _) => await RefreshAsync();
        NewChangeButton.Click += async (_, _) => await CreateChangeAsync();
        CorrectButton.Click += async (_, _) => await CreateChangeAsync(true);
        EvaluateButton.Click += async (_, _) => await EvaluateAsync();
        PreviewCsvButton.Click += async (_, _) => await PreviewCsvAsync();
        SubmitButton.Click += async (_, _) =>
        {
            if (Allow("submit")) await MutateAsync(ChangePath + "/submit", JsonSerializer.SerializeToElement(new { }), Revision);
        };
        ApproveButton.Click += async (_, _) => await DecideAsync(true);
        RejectButton.Click += async (_, _) => await DecideAsync(false);
        EvidenceButton.Click += async (_, _) => await ShowEvidenceAsync();
        CompareRunsButton.Click += async (_, _) => await CompareRunsAsync();
        CopyReferenceButton.Click += (_, _) =>
        {
            if (!HasSelection) return;
            try { Clipboard.SetText($"{ChangeId} / 개정 {Revision} / 평가 {RunId}"); StatusText.Text = "선택한 요청 참조를 복사했습니다."; }
            catch (System.Runtime.InteropServices.ExternalException error) { ShowError(error); }
        };
        RecoveryButton.Click += async (_, _) => await MutateAsync(null, default, null);
        EvaluationGrid.SelectionChanged += async (_, _) =>
        {
            if (EvaluationGrid.SelectedItem is CaseRow row && HasSelection) await ShowCaseAsync(row);
        };

        Columns(ComparisonGrid, ("확인 항목", nameof(ReviewField.Item), 1), ("값 / 고정 참조", nameof(ReviewField.Value), 3));
        Columns(EvaluationGrid, ("평가 사례", nameof(CaseRow.Id), 2), ("판정", nameof(CaseRow.Outcome), 1),
            ("해석 상태", nameof(CaseRow.Resolution), 1), ("적용 출처", nameof(CaseRow.Source), 2));
        Columns(HistoryGrid, ("개정", nameof(HistoryRow.Revision), 0.6), ("결정", nameof(HistoryRow.Action), 1),
            ("담당자", nameof(HistoryRow.Actor), 0.8), ("기록 시각", nameof(HistoryRow.Time), 1.4), ("사유", nameof(HistoryRow.Reason), 2));
        UpdateControls();
    }

    private static void Columns(DataGrid grid, params (string Title, string Path, double Weight)[] columns)
    {
        grid.AutoGenerateColumns = false;
        grid.Columns.Clear();
        foreach (var (title, path, weight) in columns)
            grid.Columns.Add(new DataGridTextColumn { Header = title, Binding = new Binding(path), Width = new DataGridLength(weight, DataGridLengthUnitType.Star), MinWidth = 65 });
    }

    private async Task ConnectAsync()
    {
        if (busy) return;
        var value = TokenInput.Password;
        TokenInput.Clear();
        LoginStatus.Text = "작업공간을 확인하고 있습니다…";
        SetBusy(true);
        WorkspaceClient? candidate = null;
        try
        {
            var testStore = Environment.GetEnvironmentVariable("CASEPROOF_DESKTOP_STATE_DIR");
            candidate = new WorkspaceClient(EndpointInput.Text, value, string.IsNullOrWhiteSpace(testStore) ? null : Path.GetFullPath(testStore));
            await candidate.ConnectAsync(closing.Token);
            client?.Dispose();
            client = candidate;
            candidate = null;
            var actor = client.Catalog.Field("actor");
            ActorText.Text = $"{actor.Text("actor_id")}  /  {string.Join(" · ", actor.Field("roles").Items().Select(r => RoleName(r.Value())))}";
            ConnectionText.Text = $"{actor.Text("tenant_id")}  ·  {client.Endpoint.Authority}";
            LoginPane.Visibility = Visibility.Collapsed;
            WorkspacePane.Visibility = Visibility.Visible;
            LoginStatus.Text = "";
            await RefreshCoreAsync();
            if (ActualWidth > 950) SearchInput.Focus();
        }
        catch (Exception error) { ShowError(error); }
        finally { candidate?.Dispose(); SetBusy(false); }
    }

    private void SignOut(string message)
    {
        generation++;
        reading = false;
        client?.Dispose();
        client = null;
        queue.Clear();
        SearchInput.Text = "";
        FilterInput.SelectedIndex = 0;
        FilterQueue();
        ClearChange();
        WorkspacePane.Visibility = Visibility.Collapsed;
        LoginPane.Visibility = Visibility.Visible;
        ActorText.Text = "";
        ConnectionText.Text = "";
        StatusText.Text = "";
        LoginStatus.Text = message;
        TokenInput.Clear();
        TokenInput.Focus();
        UpdateControls();
    }

    private void ShowError(Exception error)
    {
        if (closing.IsCancellationRequested) return;
        if (error is WorkspaceException { Unauthorized: true } && client is not null)
        {
            SignOut("현재 계정의 접근을 확인할 수 없습니다. 유효한 역할로 다시 연결하세요.");
            return;
        }
        var copy = error switch
        {
            TaskCanceledException => "서버 응답 시간이 지났습니다. 연결 또는 원래 요청 상태를 확인하세요.",
            System.Net.Http.HttpRequestException => "서버에 연결할 수 없습니다. 서버 주소와 실행 상태를 확인하세요.",
            WorkspaceException problem => Explain(problem.Code, problem.Message),
            _ => error.Message
        };
        if (client is null) LoginStatus.Text = copy;
        else StatusText.Text = copy;
    }

    private static string Explain(string reason, string fallback = "현재 조건에서는 이 조작을 수행할 수 없습니다.") => reason switch
    {
        "SEPARATION_OF_DUTIES" => "요청자·현업 검토자·최종 승인자는 서로 다른 담당자여야 합니다.",
        "REQUESTER_ONLY" => "원래 요청자만 초안을 평가하거나 현업 검토로 보낼 수 있습니다.",
        "STALE_REVISION" => "선택한 요청의 개정이 바뀌었습니다. 최신 상태에서 근거를 다시 확인하세요.",
        "RELEASE_GATE_BLOCKED" or "GATE_BLOCKED" => "전체 평가가 승인 기준을 충족하지 못했습니다.",
        "EVALUATION_INCOMPLETE" => "전체 사례 평가를 완료하고 미확정 사례를 확인하세요.",
        "SOURCE_NOT_ELIGIBLE" => "현재 출처가 적격하지 않습니다. 선택한 조항과 출처 상태를 확인하세요.",
        "INVALID_STATUS" => "현재 검토 단계에서 할 수 있는 조작을 확인하세요.",
        "FORBIDDEN" => "현재 계정에 이 단계의 조작 권한이 없습니다.",
        "REQUEST_CONTEXT_CHANGED" => "요청을 보낸 원래 서버 작업공간에서 복구하세요.",
        "NOT_FOUND" => "요청을 찾을 수 없습니다. 목록을 확인하거나 최신 CaseProof 서버에 연결하세요.",
        _ => fallback
    };

    private static string RoleName(string role) => role switch
    {
        "ANALYST" => "요청자", "DOMAIN_REVIEWER" => "현업 검토자", "RELEASE_APPROVER" => "최종 승인자",
        "AUDITOR" => "감사자", _ => role
    };

    private static string PhaseName(string phase) => phase switch
    {
        "DRAFT" => "초안 · 평가", "PENDING_DOMAIN_REVIEW" => "현업 검토 대기", "PENDING_RELEASE" => "최종 승인 대기",
        "APPROVED_FOR_DEMO" => "데모 승인 완료", "REJECTED" => "반려", _ => phase
    };

    private static string ResultName(string value) => value switch
    {
        "VALID" => "검증됨", "INVALID" => "무결성 실패", "LEGACY_UNVERIFIED" => "이전 형식 · 미검증",
        "PASS" => "통과", "FAIL" => "실패", "BLOCK" or "BLOCKED" => "차단", "COMPLETE" => "완료", "INCOMPLETE" => "미완료",
        "INCONCLUSIVE" => "판정 보류", "ELIGIBLE" => "적격", "RESOLVED" => "규칙 확인", "NOT_CONFIGURED" => "미설정",
        "NOT_APPLICABLE" => "해당 없음", "" => "—", _ => value
    };

    private bool Allow(string action) => HasSelection && review.Field("actions").Field(action).Flag("allowed");
    private bool IsReviewStage => Phase is "PENDING_DOMAIN_REVIEW" or "PENDING_RELEASE";
    private string DecisionAction(bool approve) => (Phase == "PENDING_RELEASE" ? "release_" : "domain_") + (approve ? "approve" : "reject");

    private void SetBusy(bool value) { busy = value; UpdateControls(); }

    private void UpdateControls()
    {
        LoginButton.IsEnabled = !busy;
        SwitchRoleButton.IsEnabled = !busy;
        RefreshButton.IsEnabled = client is not null && !busy;
        QueueList.IsEnabled = !busy;
        var pending = false;
        var sameContext = false;
        var storageAvailable = true;
        if (client is not null)
        {
            try { (pending, sameContext) = client.Pending(); }
            catch (IOException error) { storageAvailable = false; StatusText.Text = error.Message; }
        }
        RecoveryButton.Visibility = pending ? Visibility.Visible : Visibility.Collapsed;
        RecoveryButton.IsEnabled = !busy && !reading && pending && sameContext && client?.CanWrite == true;
        RecoveryButton.ToolTip = pending && !sameContext ? "원래 요청을 보낸 서버 작업공간에 다시 연결하세요." : "서버에 저장된 원래 요청부터 확인합니다.";
        var canWrite = client?.CanWrite == true && !busy && !reading && !pending && storageAvailable;
        NewChangeButton.Visibility = client?.HasRole("ANALYST") == true ? Visibility.Visible : Visibility.Collapsed;
        NewChangeButton.IsEnabled = canWrite;
        CorrectButton.Visibility = Phase == "REJECTED" && client?.HasRole("ANALYST") == true ? Visibility.Visible : Visibility.Collapsed;
        CorrectButton.IsEnabled = canWrite;
        var editable = Phase == "DRAFT" && client?.HasRole("ANALYST") == true;
        EvaluateButton.Visibility = PreviewCsvButton.Visibility = SubmitButton.Visibility = editable ? Visibility.Visible : Visibility.Collapsed;
        EvaluateButton.IsEnabled = PreviewCsvButton.IsEnabled = canWrite && Allow("evaluate");
        SubmitButton.IsEnabled = canWrite && Allow("submit");
        ApproveButton.Visibility = RejectButton.Visibility = IsReviewStage ? Visibility.Visible : Visibility.Collapsed;
        ApproveButton.IsEnabled = canWrite && IsReviewStage && Allow(DecisionAction(true));
        RejectButton.IsEnabled = canWrite && IsReviewStage && Allow(DecisionAction(false));
        ApproveButton.Content = Phase == "PENDING_RELEASE" ? "데모 승인 기록" : "현업 검토 기록";
        EvidenceButton.IsEnabled = CompareRunsButton.IsEnabled = HasSelection && !reading && !busy;
        CompareRunsButton.Visibility = CopyReferenceButton.Visibility = HasSelection ? Visibility.Visible : Visibility.Collapsed;
        if (pending && !sameContext) DecisionStatus.Text = "복원본에서는 기존 요청을 다시 보내지 않습니다. 원래 작업공간으로 돌아가세요.";
        else if (pending) DecisionStatus.Text = "저장 결과 확인 대기 · 원래 요청 복구를 이용하세요.";
        else if (client is not null && !client.CanWrite) DecisionStatus.Text = "읽기 전용 · 이 서버의 요청 복구 컨텍스트를 확인하지 못했습니다.";
        else if (reading) DecisionStatus.Text = "현재 개정과 승인 조건을 확인하고 있습니다…";
        else if (!HasSelection) DecisionStatus.Text = "요청 목록에서 검토할 항목을 선택하세요.";
        else if (IsReviewStage && !Allow(DecisionAction(true)))
            DecisionStatus.Text = Explain(review.Field("actions").Field(DecisionAction(true)).Text("reason"));
        else if (Phase == "DRAFT" && !Allow("submit"))
            DecisionStatus.Text = Explain(review.Field("actions").Field("submit").Text("reason"), "전체 평가 결과를 확인한 후 현업 검토로 보내세요.");
        else DecisionStatus.Text = Phase == "APPROVED_FOR_DEMO" ? "결정 당시 평가·출처를 근거에서 확인할 수 있습니다." : "선택한 개정과 평가 실행을 기준으로 작업합니다.";
    }

    private void FilterQueue()
    {
        if (QueueList is null || SearchInput is null || FilterInput is null || QueueSummary is null) return;
        var term = SearchInput.Text.Trim();
        var filter = (FilterInput.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "";
        var filtered = queue.Where(row => (filter.Length == 0 || row.StatusCode == filter)
            && (term.Length == 0 || $"{row.Title} {row.Id} {row.Pack}".Contains(term, StringComparison.OrdinalIgnoreCase))).ToList();
        updatingQueue = true;
        QueueList.ItemsSource = filtered;
        QueueList.SelectedItem = filtered.FirstOrDefault(row => row.Id == ChangeId);
        updatingQueue = false;
        QueueSummary.Text = term.Length > 0 || filter.Length > 0 ? $"검색 결과 {filtered.Count}건 / 전체 {queue.Count}건" : $"전체 {queue.Count}건";
    }

    private async Task RefreshAsync()
    {
        if (busy || client is null) return;
        var previous = ChangeId;
        SetBusy(true);
        try
        {
            await RefreshCoreAsync();
            if (previous.Length != 0 && queue.Any(row => row.Id == previous)) await LoadChangeAsync(previous);
            else if (previous.Length != 0) ClearChange();
            StatusText.Text = "최신 요청 목록을 확인했습니다.";
        }
        catch (Exception error) { ShowError(error); }
        finally { SetBusy(false); }
    }

    private async Task RefreshCoreAsync()
    {
        var session = client!;
        try
        {
            var results = await session.ChangesAsync(count => QueueSummary.Text = $"조회 중 · {count}건 수신", closing.Token);
            queue = results.Select(row => new ChangeRow(row.Text("change_id"), row.Text("title"), PhaseName(row.Text("status")), row.Text("status"),
                row.Number("revision").ToString(CultureInfo.InvariantCulture), row.Text("pack_version_id"))).ToList();
            FilterQueue();
        }
        catch
        {
            QueueSummary.Text = "목록 조회 실패 · 새로고침으로 다시 확인";
            ClearChange();
            throw;
        }
    }

    private void ClearChange()
    {
        selected = review = execution = default;
        ChangeTitle.Text = "검토할 요청을 선택하세요";
        ChangeMeta.Text = "";
        StageText.Text = "";
        ComparisonGrid.ItemsSource = EvaluationGrid.ItemsSource = HistoryGrid.ItemsSource = null;
        ProofStatus.Text = "선택한 요청의 근거가 표시됩니다.";
        ProofContent.Text = "";
        UpdateControls();
    }

    private async Task LoadChangeAsync(string id)
    {
        if (client is null || !Guid.TryParseExact(id, "D", out _)) return;
        var session = client;
        var request = ++generation;
        var previouslySelected = ChangeId;
        reading = true;
        ClearChange();
        ChangeTitle.Text = "요청과 판정 근거를 불러오는 중…";
        var path = $"/api/v1/changes/{id}";
        try
        {
            for (var attempt = 0; attempt < 2; attempt++)
            {
                var reviewTask = session.GetAsync(path + "/review", closing.Token);
                var snapshotTask = session.GetAsync(path, closing.Token);
                await Task.WhenAll(reviewTask, snapshotTask);
                if (request != generation || session != client) return;
                var snapshot = snapshotTask.Result.Field("snapshot");
                var currentReview = reviewTask.Result;
                if (snapshotTask.Result.Text("historical_integrity") != "VALID" || currentReview.Text("historical_integrity") != "VALID")
                {
                    ChangeTitle.Text = "안전하게 확인할 수 없는 기록입니다.";
                    ChangeMeta.Text = ResultName(currentReview.Text("historical_integrity", snapshotTask.Result.Text("historical_integrity")));
                    return;
                }
                if (snapshot.Text("change_id") != id || currentReview.Text("change_id") != id || snapshot.Number("revision") != currentReview.Number("revision"))
                    continue;
                selected = snapshot;
                review = currentReview;
                execution = snapshotTask.Result.Field("latest_run");
                if (id != previouslySelected) ReviewTabs.SelectedIndex = 0;
                RenderChange();
                StatusText.Text = "현재 개정의 승인 조건을 확인했습니다.";
                return;
            }
            throw new InvalidDataException("조회 중 요청의 개정이 바뀌었습니다. 목록에서 다시 선택하세요.");
        }
        catch (Exception error)
        {
            if (request != generation || session != client) return;
            ClearChange();
            if (error is WorkspaceException { Code: "INVALID_RESPONSE" })
                StatusText.Text = "Windows 검토를 지원하는 최신 CaseProof 서버인지 확인하세요.";
            else ShowError(error);
        }
        finally { if (request == generation) { reading = false; UpdateControls(); } }
    }

    private void RenderChange()
    {
        var evaluation = review.Field("evaluation");
        ChangeTitle.Text = selected.Text("title");
        ChangeMeta.Text = $"{ChangeId}  /  개정 {Revision}  /  {selected.Text("pack_version_id")}  /  평가 {(RunId.Length == 0 ? "미실행" : RunId)}";
        StageText.Text = PhaseName(Phase);
        ComparisonGrid.ItemsSource = new ReviewField[]
        {
            new("적용 규칙", selected.Text("rule_key")), new("상품 / 작업", $"{selected.Text("product_id")}  /  {selected.Text("workflow")}"),
            new("전체 평가", $"{ResultName(evaluation.Text("completion"))}  /  {ResultName(evaluation.Text("gate_summary"))}"),
            new("현재 검토 기준", ResultName(evaluation.Text("current_gate_summary"))),
            new("현재 출처 적격성", ResultName(review.Text("current_approval_eligibility"))),
            new("요청자", selected.Text("requester_id")), new("출처 묶음", selected.Text("source_bundle_id")),
            new("평가 모음", selected.Text("suite_version_id"))
        };
        EvaluationGrid.ItemsSource = execution.Field("case_results").Items().Select(row => new CaseRow(row.Text("case_id"),
            ResultName(row.Text("verdict")), ResultName(row.Text("resolution_status")),
            row.Field("source_refs").Items().Any() ? "선택해 출처 열기" : "확정 출처 없음", row)).ToList();
        HistoryGrid.ItemsSource = review.Field("decisions").Items().Select(row => new HistoryRow($"{row.Number("input_revision")} → {row.Number("output_revision")}",
            $"{(row.Text("stage") == "DOMAIN" ? "현업 검토" : "최종 결정")} · {(row.Text("decision") == "APPROVE" ? "승인" : "반려")}",
            row.Text("actor_id"), row.Text("occurred_at"), row.Text("reason"))).ToList();
        RenderProof();
        FilterQueue();
    }

    private void RenderProof()
    {
        var seal = review.Field("seal");
        ProofTitle.Text = seal.ValueKind == JsonValueKind.Object ? "결정 당시 근거" : "검토 근거";
        ProofStatus.Text = $"기록 {ResultName(review.Text("historical_integrity"))}  ·  현재 출처 {ResultName(review.Text("current_approval_eligibility"))}";
        var output = new StringBuilder();
        output.AppendLine($"현재 개정  {Revision}");
        output.AppendLine($"외부 앵커  {ResultName(review.Text("external_anchor"))}");
        if (RunId.Length > 0) output.AppendLine($"현재 평가 실행  {RunId}");
        if (seal.ValueKind == JsonValueKind.Object)
        {
            output.AppendLine().AppendLine($"승인 당시 개정  {seal.Number("approved_revision")}")
                .AppendLine($"검토 대상 개정  {seal.Number("preapproval_revision")}")
                .AppendLine($"고정 평가 실행  {seal.Text("run_id")}")
                .AppendLine($"고정 출처 묶음  {seal.Text("source_bundle_id")}")
                .AppendLine($"승인 봉인 SHA-256  {review.Text("envelope_sha256")}");
            foreach (var source in seal.Field("sources").Items())
                output.AppendLine($"출처 버전  {source.Text("policy_version_id")}");
            var note = review.Field("decisions").Items().FirstOrDefault(item => item.Text("id") == seal.Text("decision_id"));
            if (note.ValueKind == JsonValueKind.Object)
                output.AppendLine().AppendLine($"결정자  {note.Text("actor_id")}").AppendLine($"결정 시각  {note.Text("occurred_at")}").AppendLine($"사유  {note.Text("reason")}");
        }
        else
        {
            foreach (var reason in review.Field("evaluation").Field("gate_reasons").Items())
                output.AppendLine(Explain(reason.Value(), reason.Value()));
            output.AppendLine("평가 사례를 선택하면 해당 규칙과 출처를 엽니다.");
        }
        ProofContent.Text = output.ToString().TrimEnd();
    }

    private async Task ShowEvidenceAsync()
    {
        if (client is null || !HasSelection) return;
        var id = ChangeId;
        await LoadChangeAsync(id);
        if (ChangeId == id) OpenProof();
    }

    private async Task ShowCaseAsync(CaseRow row)
    {
        if (client is null || RunId.Length == 0) return;
        var request = generation;
        var session = client;
        var run = RunId;
        var path = ChangePath;
        OpenProof();
        ProofTitle.Text = "평가 사례 근거";
        ProofStatus.Text = row.Id + "  ·  " + row.Outcome;
        ProofContent.Text = "출처와 관측 기준을 확인하고 있습니다…";
        try
        {
            var data = await session.GetAsync($"{path}/evaluation-runs/{run}/coverage", closing.Token);
            if (request != generation || client != session || EvaluationGrid.SelectedItem is not CaseRow active || active.Id != row.Id) return;
            var @case = data.Field("cases").Items().FirstOrDefault(item => item.Text("case_id") == row.Id);
            var output = new StringBuilder().AppendLine($"실행  {run}").AppendLine($"판정  {row.Outcome}");
            if (@case.ValueKind == JsonValueKind.Object)
            {
                output.AppendLine($"업무 기준일  {@case.Text("basis_date")}").AppendLine($"관측 기준  {@case.Text("recorded_as_of")}")
                    .AppendLine($"적용 규칙  {@case.Text("selected_rule_id")}");
                foreach (var source in @case.Field("candidates").Items())
                    output.AppendLine($"{source.Text("rule_id")} / {source.Text("clause_id")} / {source.Text("policy_version")}  ·  {(source.Flag("eligible") ? "적격" : "제외")}");
            }
            else output.AppendLine("저장된 조항별 기록이 없습니다. 기록된 결과 해시를 함께 확인하세요.");
            foreach (var source in row.Data.Field("source_refs").Items())
                output.AppendLine($"고정 출처  {source.Text("id")}  /  {source.Text("payload_sha256")}");
            foreach (var key in new[] { "input_sha256", "output_sha256" })
            {
                var value = row.Data.Field(key).Value();
                if (value.Length > 0) output.AppendLine($"{key}  {value}");
            }
            ProofContent.Text = output.ToString().TrimEnd();
        }
        catch (Exception error)
        {
            if (request != generation || client != session) return;
            ProofContent.Text = "사례 근거를 불러오지 못했습니다. 다시 선택하세요.";
            ShowError(error);
        }
    }

    private async Task CompareRunsAsync()
    {
        if (busy || client is null || !HasSelection) return;
        var selection = generation;
        var session = client;
        var path = ChangePath;
        try
        {
            var history = await session.GetAsync(path + "/evaluation-runs", closing.Token);
            if (selection != generation || client != session) return;
            var choices = history.Field("runs").Items().Select(run => new RunChoice(run.Text("id"),
                $"개정 {run.Number("recorded_revision")}  ·  {ResultName(run.Text("gate_summary"))}  ·  {run.Text("id")}")).ToList();
            if (choices.Count < 2) { StatusText.Text = "저장 평가 비교에는 실행 두 건이 필요합니다."; return; }
            var baseline = new ComboBox { ItemsSource = choices, DisplayMemberPath = nameof(RunChoice.Label), SelectedIndex = 1 };
            var candidate = new ComboBox { ItemsSource = choices, DisplayMemberPath = nameof(RunChoice.Label), SelectedIndex = 0 };
            if (!Prompt("저장 평가 비교", "기존 실행 두 건의 판정과 근거 변경을 확인합니다.", "비교 열기", "CompareRunsConfirmButton",
                [("기준 평가", baseline), ("비교 평가", candidate)], () => baseline.SelectedIndex != candidate.SelectedIndex ? null : "서로 다른 실행을 선택하세요.")) return;
            if (baseline.SelectedItem is not RunChoice first || candidate.SelectedItem is not RunChoice second) return;
            var result = await session.GetAsync(path + "/evaluation-runs/compare?baseline_run_id=" + Uri.EscapeDataString(first.Id)
                + "&candidate_run_id=" + Uri.EscapeDataString(second.Id), closing.Token);
            if (selection != generation || client != session) return;
            OpenProof();
            ProofTitle.Text = "저장 평가 비교";
            ProofStatus.Text = "고정된 두 실행의 차이";
            ProofContent.Text = FormatComparison(result, first, second);
        }
        catch (Exception error) { if (selection == generation && client == session) ShowError(error); }
    }

    private static string FormatComparison(JsonElement result, RunChoice left, RunChoice right)
    {
        var output = new StringBuilder().AppendLine($"기준  {left.Label}").AppendLine($"대상  {right.Label}");
        var counts = result.Field("changed_counts");
        output.AppendLine($"달라진 사례  {counts.Number("any_changed")}건");
        if (result.Text("mode") != "SAME_CONTEXT")
            output.AppendLine("실행 조건이 같지 않습니다. 입력과 평가 조건을 확인하세요.");
        foreach (var item in result.Field("rows").Items())
        {
            var changed = item.Field("changes");
            if (changed.ValueKind != JsonValueKind.Object || !changed.EnumerateObject().Any(field => field.Value.ValueKind == JsonValueKind.True)) continue;
            var baseline = ResultName(item.Field("baseline").Text("verdict"));
            var candidate = ResultName(item.Field("candidate").Text("verdict"));
            output.AppendLine().AppendLine($"{item.Text("case_id")}  ·  {baseline} → {candidate}");
            foreach (var (key, label) in new[] { ("presence_changed", "사례 구성"), ("input_changed", "입력"),
                ("output_changed", "결과"), ("source_refs_changed", "출처"), ("result_state_changed", "판정 상태") })
                if (changed.Flag(key)) output.AppendLine($"  {label} 변경");
        }
        return output.ToString().TrimEnd();
    }

    private async Task CreateChangeAsync(bool correction = false)
    {
        if (client is null || !client.HasRole("ANALYST")) return;
        var presets = client.Catalog.Field("presets").Items().ToList();
        if (correction) presets = presets.Where(preset => preset.Field("create_body").Text("suite_version_id") == selected.Text("suite_version_id")).ToList();
        if (presets.Count == 0) { StatusText.Text = "현재 요청에 맞는 합성 팩이 없습니다."; return; }
        var pack = new ComboBox { ItemsSource = presets.Select(preset => preset.Text("label")).ToList(), SelectedIndex = 0, IsEnabled = !correction };
        var title = new TextBox { MaxLength = 500, Text = correction ? selected.Text("title") + " · 시정" : "" };
        AutomationProperties.SetAutomationId(pack, "NewChangePackInput");
        AutomationProperties.SetAutomationId(title, "NewChangeTitleInput");
        if (!Prompt(correction ? "반려 요청 시정" : "새 변경 요청", "등록된 합성 팩에서 새 검토 초안을 시작합니다.", "초안 저장", "NewChangeConfirmButton",
            [("합성 팩", pack), ("요청 제목", title)], () => title.Text.Trim().Length == 0 ? "요청 제목을 입력하세요." : null)) return;
        var payload = presets[pack.SelectedIndex].Field("create_body").EnumerateObject().ToDictionary(item => item.Name, item => item.Value, StringComparer.Ordinal);
        payload["title"] = JsonSerializer.SerializeToElement(title.Text.Trim());
        if (correction)
        {
            payload["parent_change_id"] = JsonSerializer.SerializeToElement(ChangeId);
            payload["parent_relation"] = JsonSerializer.SerializeToElement("CORRECTS_REJECTED");
        }
        await MutateAsync("/api/v1/changes", JsonSerializer.SerializeToElement(payload), null);
    }

    private async Task EvaluateAsync()
    {
        if (client is null || !Allow("evaluate")) return;
        var preset = client.Catalog.Field("presets").Items().FirstOrDefault(item => item.Field("create_body").Text("suite_version_id") == selected.Text("suite_version_id"));
        var cases = preset.Field("case_inputs").Items().ToList();
        if (cases.Count == 0) { StatusText.Text = "등록된 합성 사례를 찾지 못했습니다. CSV 점검 또는 서버 팩을 확인하세요."; return; }
        var entries = cases.Select(item => new TextBox { Text = item.Number("claim_days").ToString(CultureInfo.InvariantCulture), MaxLength = 4 }).ToList();
        for (var i = 0; i < entries.Count; i++) AutomationProperties.SetAutomationId(entries[i], $"EvaluationInput{i}");
        var fields = cases.Select((item, index) => ($"{item.Text("case_id")} · 주장 일수", (Control)entries[index])).ToArray();
        static bool Days(string text, out int number) => int.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out number) && number <= 9999;
        if (!Prompt("전체 모음 평가", "등록된 전체 합성 사례를 실행합니다. 각 사례의 주장 일수를 입력하세요.", "평가 실행", "EvaluationConfirmButton",
            fields, () => entries.All(entry => Days(entry.Text, out _)) ? null : "주장 일수를 0–9999 사이 정수로 입력하세요.")) return;

        var inputs = cases.Select((item, index) => new
        {
            case_id = item.Text("case_id"), claim_days = int.Parse(entries[index].Text, CultureInfo.InvariantCulture), case_context = item.Field("case_context")
        }).ToArray();
        var payload = JsonSerializer.SerializeToElement(new { suite_version_id = selected.Text("suite_version_id"), case_inputs = inputs });
        await MutateAsync(ChangePath + "/evaluation-runs", payload, Revision);
    }

    private async Task PreviewCsvAsync()
    {
        if (client is null || !Allow("evaluate")) return;
        var chooser = new OpenFileDialog { Filter = "UTF-8 합성 사례 CSV (*.csv)|*.csv", CheckFileExists = true, Multiselect = false };
        if (chooser.ShowDialog(this) != true) return;
        var session = client;
        var change = ChangeId;
        var revision = Revision;
        JsonElement evaluation = default;
        SetBusy(true);
        try
        {
            using var stream = new FileStream(chooser.FileName, FileMode.Open, FileAccess.Read, FileShare.Read);
            if (stream.Length > 256 * 1024) throw new InvalidDataException("256 KiB 이하의 합성 사례 CSV를 선택하세요.");
            var contents = new byte[stream.Length];
            await stream.ReadExactlyAsync(contents, closing.Token);
            var preview = await session.PreviewCsvAsync(change, revision, contents, closing.Token);
            if (client != session || Revision != revision || ChangeId != change) return;
            if (!preview.Flag("ready"))
            {
                ProofTitle.Text = "CSV 점검 결과";
                ProofStatus.Text = "오류 · 수정 후 다시 선택";
                ProofContent.Text = string.Join(Environment.NewLine, preview.Field("errors").Items().Select(error =>
                    $"행 {error.Field("row").Value()}  ·  {error.Text("column")}  ·  {error.Text("code")}  ·  {error.Text("case_id")}"));
                OpenProof();
                return;
            }
            var candidate = preview.Field("evaluation");
            if (preview.Number("revision") != revision || candidate.Text("suite_version_id") != selected.Text("suite_version_id") || candidate.Field("case_inputs").ValueKind != JsonValueKind.Array)
                throw new InvalidDataException("CSV 점검의 개정·평가 모음이 현재 요청과 일치하지 않습니다.");
            if (Prompt("합성 CSV 점검 완료", $"전체 사례 {candidate.Field("case_inputs").GetArrayLength()}건을 확인했습니다. 이 입력으로 평가를 실행할 수 있습니다.",
                "평가 실행", "EvaluationConfirmButton", [], () => null)) evaluation = candidate;
        }
        catch (Exception error) { ShowError(error); }
        finally { SetBusy(false); }
        if (evaluation.ValueKind == JsonValueKind.Object && client == session && ChangeId == change && Revision == revision)
            await MutateAsync(ChangePath + "/evaluation-runs", evaluation, revision);
    }

    private async Task DecideAsync(bool approve)
    {
        if (!IsReviewStage || !Allow(DecisionAction(approve))) return;
        var reason = new TextBox { AcceptsReturn = true, TextWrapping = TextWrapping.Wrap, MinHeight = 105, MaxLength = 500 };
        AutomationProperties.SetAutomationId(reason, "DecisionReasonInput");
        var title = approve ? Phase == "PENDING_RELEASE" ? "데모 승인 기록" : "현업 검토 기록" : "반려 기록";
        var path = ChangePath + (Phase == "PENDING_RELEASE" ? "/release-decision" : "/domain-decision");
        if (!Prompt(title, $"{ChangeId} · 개정 {Revision} · 평가 {RunId}", "결정 저장", "DecisionConfirmButton",
            [("검토 사유 (8–500자)", reason)], () => reason.Text.Trim().Length < 8 ? "검토 사유를 8자 이상 입력하세요." : null)) return;
        await MutateAsync(path, JsonSerializer.SerializeToElement(new { decision = approve ? "APPROVE" : "REJECT", reason = reason.Text.Trim() }), Revision);
    }

    private async Task MutateAsync(string? path, JsonElement body, int? revision)
    {
        if (busy || client is null) return;
        var session = client;
        SetBusy(true);
        StatusText.Text = path is null ? "서버에서 원래 요청의 저장 결과를 확인하고 있습니다…" : "서버에 기록하고 있습니다…";
        try
        {
            var result = path is null ? await session.RecoverAsync(closing.Token) : await session.WriteAsync(path, body, revision, closing.Token);
            var receipt = result.Replayed || path is null ? "원래 요청의 저장 결과를 확인했습니다" : "저장했습니다";
            try
            {
                await RefreshCoreAsync();
                await LoadChangeAsync(result.ChangeId);
            }
            catch (Exception error)
            {
                ShowError(error);
                if (client == session) StatusText.Text = $"{receipt} · 개정 {result.Revision}. 최신 화면을 새로고침하세요.";
                return;
            }
            if (client != session) return;
            if (path?.EndsWith("-decision", StringComparison.Ordinal) == true || path is null && Phase == "APPROVED_FOR_DEMO") OpenProof();
            StatusText.Text = $"{receipt} · {result.ChangeId} / 개정 {result.Revision}";
        }
        catch (Exception error)
        {
            var pending = false;
            try { pending = session.Pending().Exists; }
            catch (IOException) { }
            if (!pending && error is WorkspaceException { Code: "STALE_REVISION" } && HasSelection) await LoadChangeAsync(ChangeId);
            ShowError(error);
            if (pending && client == session) StatusText.Text = "저장 결과 확인 대기 · 원래 요청 복구를 이용하세요.";
        }
        finally { SetBusy(false); }
    }

    private void ApplyPaneLayout()
    {
        if (QueueColumn is null || ProofColumn is null) return;
        var showQueue = queueOpen;
        var showProof = proofOpen;
        if (ActualWidth < 1060 && showProof) showQueue = false;
        QueuePane.Visibility = showQueue ? Visibility.Visible : Visibility.Collapsed;
        ProofPane.Visibility = showProof ? Visibility.Visible : Visibility.Collapsed;
        QueueColumn.MinWidth = showQueue ? 170 : 0;
        ProofColumn.MinWidth = showProof ? 222 : 0;
        QueueColumn.Width = showQueue ? new GridLength(ActualWidth < 900 ? Math.Min(220, queueWidth) : queueWidth) : new GridLength(0);
        ProofColumn.Width = showProof ? new GridLength(ActualWidth < 900 ? Math.Min(240, proofWidth) : proofWidth) : new GridLength(0);
        QueueSplitterColumn.Width = new GridLength(showQueue ? 5 : 0);
        ProofSplitterColumn.Width = new GridLength(showProof ? 5 : 0);
        ToggleQueueButton.Content = showQueue ? "목록 접기" : "목록 열기";
        ToggleProofButton.Content = showProof ? "근거 접기" : "근거 열기";
    }

    private void ToggleQueue()
    {
        if (QueuePane.Visibility == Visibility.Visible)
        {
            queueWidth = Math.Max(170, QueueColumn.ActualWidth);
            queueOpen = false;
        }
        else { queueOpen = true; if (ActualWidth < 1060) proofOpen = false; }
        ApplyPaneLayout();
        if (queueOpen) QueueList.Focus();
    }

    private void ToggleProof()
    {
        if (!proofOpen) { OpenProof(); return; }
        proofWidth = Math.Max(222, ProofColumn.ActualWidth);
        proofOpen = false;
        ApplyPaneLayout();
        ToggleProofButton.Focus();
    }

    private void OpenProof() { proofOpen = true; ApplyPaneLayout(); }

    private async void HandleShortcut(object sender, KeyEventArgs key)
    {
        if (client is null) return;
        if (key.Key == Key.F5 && !busy) { key.Handled = true; await RefreshAsync(); }
        else if (key.Key == Key.Escape && proofOpen) { key.Handled = true; ToggleProof(); }
        else if (key.Key == Key.F && Keyboard.Modifiers == ModifierKeys.Control)
        {
            key.Handled = true;
            if (QueuePane.Visibility != Visibility.Visible) ToggleQueue();
            SearchInput.Focus(); SearchInput.SelectAll();
        }
        else if (key.Key == Key.N && Keyboard.Modifiers == ModifierKeys.Control && NewChangeButton.IsEnabled)
        { key.Handled = true; await CreateChangeAsync(); }
    }
}
