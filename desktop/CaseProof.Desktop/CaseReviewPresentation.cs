using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Windows.Controls;

namespace CaseProof.Desktop;

public partial class MainWindow
{
    private async Task<(Dictionary<string, JsonElement> Cases, string Notice)> ReadCaseCoverageAsync(
        WorkspaceClient session, string path, string run)
    {
        Dictionary<string, JsonElement> cases = new(StringComparer.Ordinal);
        if (run.Length == 0) return (cases, "");

        try
        {
            var coverage = await session.GetAsync($"{path}/evaluation-runs/{Uri.EscapeDataString(run)}/coverage", closing.Token);
            if (coverage.Text("run_id") != run)
                return (cases, "현재 평가와 일치하는 조항 근거를 확인하지 못했습니다. 새로고침하세요.");
            if (coverage.Text("availability") != "AVAILABLE")
                return (cases, "이 평가에 보관된 조항별 근거가 없습니다.");

            foreach (var item in coverage.Field("cases").Items())
                cases[item.Text("case_id")] = item;
            return (cases, "");
        }
        catch (WorkspaceException error) when (!error.Unauthorized)
        {
            return (cases, Explain(error.Code, "조항 근거 조회에 실패했습니다. 새로고침으로 다시 확인하세요."));
        }
        catch (HttpRequestException)
        {
            return (cases, "조항 근거를 불러오지 못했습니다. 연결을 확인하고 새로고침하세요.");
        }
        catch (TaskCanceledException) when (!closing.IsCancellationRequested)
        {
            return (cases, "조항 근거 응답 시간이 지났습니다. 새로고침하세요.");
        }
    }

    private CaseRow CreateCaseRow(JsonElement data)
    {
        var id = data.Text("case_id");
        var code = data.Text("verdict");
        caseCoverage.TryGetValue(id, out var coverage);
        var rule = coverage.Text("selected_rule_id");
        var candidate = coverage.Field("candidates").Items()
            .FirstOrDefault(item => rule.Length > 0 && item.Text("rule_id") == rule && item.Flag("eligible"));
        var clause = candidate.Text("clause_id");
        var source = clause.Length > 0
            ? $"{clause} / {candidate.Text("policy_version", "버전 없음")}"
            : coverage.ValueKind == JsonValueKind.Object ? "미확정" : "조항 조회 불가";
        return new CaseRow(id, code, ResultName(code), source, coverage.Text("basis_date", "미기록"), data, coverage);
    }

    private void FilterCases(bool initial = false, string? previousCase = null)
    {
        var filter = (CaseFilterInput.SelectedItem as ComboBoxItem)?.Tag?.ToString();
        var visible = caseRows.Where(row => filter switch
        {
            "ATTENTION" => row.OutcomeCode != "PASS",
            "PASS" => row.OutcomeCode == "PASS",
            _ => true
        }).ToList();
        var keep = previousCase ?? (EvaluationGrid.SelectedItem as CaseRow)?.Id;
        var selectedCase = visible.FirstOrDefault(row => row.Id == keep);
        if (initial && selectedCase is null && Phase != "APPROVED_FOR_DEMO")
            selectedCase = visible.FirstOrDefault();

        updatingCases = true;
        EvaluationGrid.ItemsSource = visible;
        EvaluationGrid.SelectedItem = selectedCase;
        updatingCases = false;

        CaseFilterSummary.Text = caseRows.Count == 0
            ? "평가 실행 없음"
            : $"표시 {visible.Count}건 / 전체 {caseRows.Count}건";
        if (HasSelection)
        {
            if (EvaluationTab.IsSelected && selectedCase is not null) RenderSelectedCase(open: false);
            else if (initial && filter is not ("ATTENTION" or "PASS")) RenderProof();
            else if (EvaluationTab.IsSelected) RenderSelectedCase(open: false);
        }
        UpdateCaseNavigation();
    }

    private CaseRow? NextAttentionCase()
    {
        var nextIndex = EvaluationGrid.SelectedIndex + 1;
        return EvaluationGrid.Items.OfType<CaseRow>().Skip(nextIndex)
            .FirstOrDefault(row => row.OutcomeCode != "PASS");
    }

    private void UpdateCaseNavigation()
    {
        CaseFilterInput.IsEnabled = !busy && !reading && caseRows.Count > 0;
        NextCaseButton.IsEnabled = !busy && !reading && NextAttentionCase() is not null;
    }

    private void RenderSelectedCase(bool open)
    {
        if (EvaluationGrid.SelectedItem is not CaseRow row)
        {
            showingCaseEvidence = false;
            EvaluationGrid.Tag = "";
            ProofTitle.Text = "사례 근거";
            ProofStatus.Text = "선택한 사례 없음";
            ProofContent.Text = EvaluationGrid.Items.Count == 0
                ? "이 필터에서 표시할 사례 근거가 없습니다."
                : "검증 사례를 선택하면 해당 근거를 표시합니다.";
            SetProofAudit(null);
            ApplyPaneLayout();
            return;
        }

        showingCaseEvidence = true;
        var output = new StringBuilder()
            .AppendLine($"조항 · 버전  {row.Source}")
            .AppendLine($"업무 기준일  {row.BasisDate}");
        var audit = new StringBuilder().AppendLine($"평가 실행  {RunId}").AppendLine($"사례  {row.Id}");
        if (row.Coverage.ValueKind == JsonValueKind.Object)
        {
            var rule = row.Coverage.Text("selected_rule_id");
            output.AppendLine($"관측 기준  {DisplayUtc(row.Coverage.Text("recorded_as_of", "미기록"))}")
                .AppendLine($"적용 규칙  {(rule.Length > 0 ? rule : "미확정")}");
            var candidates = row.Coverage.Field("candidates").Items().ToList();
            output.AppendLine(candidates.Any(candidate => rule.Length > 0 && candidate.Text("rule_id") == rule && candidate.Flag("eligible"))
                ? "출처 적격성  적격" : "출처 적격성  확인 불가");
            foreach (var candidate in candidates)
            {
                audit.AppendLine($"근거 후보  {candidate.Text("clause_id")} / {candidate.Text("policy_version")}")
                    .AppendLine($"  규칙  {candidate.Text("rule_id")} · 출처  {candidate.Text("source_id")}");
            }
            foreach (var reason in row.Coverage.Field("reason_codes").Items())
                output.AppendLine(Explain(reason.Value(), reason.Value()));
        }
        else
        {
            output.AppendLine(coverageNotice.Length > 0 ? coverageNotice : "이 사례의 조항 근거가 기록되지 않았습니다.");
        }
        output.Append($"평가 실행  {ShortId(RunId)}");

        foreach (var source in row.Data.Field("source_refs").Items())
            audit.AppendLine($"고정 출처  {source.Text("id")}").AppendLine(source.Text("payload_sha256"));
        foreach (var key in new[] { "input_sha256", "output_sha256" })
        {
            var value = row.Data.Field(key).Value();
            if (value.Length > 0) audit.AppendLine($"{key}  {value}");
        }

        ProofTitle.Text = "평가 사례 근거";
        ProofStatus.Text = $"{row.Id}  ·  {row.Outcome}";
        ProofContent.Text = output.ToString();
        EvaluationGrid.Tag = ProofContent.Text;
        SetProofAudit(audit.ToString().TrimEnd());
        if (open) OpenProof();
        else ApplyPaneLayout();
    }
}
