using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace CaseProof.Desktop;

internal static class JsonFields
{
    internal static JsonElement Field(this JsonElement value, string name) =>
        value.ValueKind == JsonValueKind.Object && value.TryGetProperty(name, out var property) ? property : default;

    internal static string Text(this JsonElement value, string name, string fallback = "") =>
        value.Field(name) is { ValueKind: JsonValueKind.String } property ? property.GetString() ?? fallback : fallback;

    internal static int Number(this JsonElement value, string name) =>
        value.Field(name) is { ValueKind: JsonValueKind.Number } property && property.TryGetInt32(out var number) ? number : 0;

    internal static bool Flag(this JsonElement value, string name) => value.Field(name).ValueKind == JsonValueKind.True;

    internal static IEnumerable<JsonElement> Items(this JsonElement value) =>
        value.ValueKind == JsonValueKind.Array ? value.EnumerateArray() : [];

    internal static string Value(this JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.String => value.GetString() ?? "",
        JsonValueKind.Null or JsonValueKind.Undefined => "",
        _ => value.GetRawText()
    };
}

internal sealed class WorkspaceException(HttpStatusCode status, string code, string message) : Exception(message)
{
    internal string Code { get; } = code;
    internal HttpStatusCode Status { get; } = status;
    internal bool Unauthorized => Status is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden;
}

internal sealed record RequestIntent(string Key, string Path, string Body, int? Revision, string Context);
internal sealed record MutationReceipt(string ChangeId, int Revision, bool Replayed);

/// <summary>Uses only the shared v1 service. Bearer credentials never enter the protected intent file.</summary>
internal sealed class WorkspaceClient : IDisposable
{
    private const string Changes = "/api/v1/changes";
    private const string QueuePage = Changes + "?limit=50";
    private readonly HttpClient http;
    private readonly string token;
    private readonly string intentDirectory;
    private byte[]? scope;
    private string context = "";
    private string? intentFile;

    internal Uri Endpoint { get; }
    internal JsonElement Catalog { get; private set; }
    internal bool CanWrite => context.Length == 64 && intentFile is not null;

    internal WorkspaceClient(string endpoint, string token, string? intentDirectory = null)
    {
        if (!Uri.TryCreate(endpoint.Trim(), UriKind.Absolute, out var uri)
            || (uri.Scheme != Uri.UriSchemeHttps && !(uri.Scheme == Uri.UriSchemeHttp && uri.IsLoopback))
            || uri.UserInfo.Length != 0 || uri.AbsolutePath != "/" || uri.Query.Length != 0 || uri.Fragment.Length != 0)
            throw new ArgumentException("서버의 기본 주소를 입력하세요. 로컬 데모는 http://127.0.0.1:8766, 원격 서버는 HTTPS를 사용합니다.");

        if (string.IsNullOrWhiteSpace(token) || token.Any(char.IsWhiteSpace))
            throw new ArgumentException("역할별 접속 토큰을 입력하세요.");

        Endpoint = uri;
        this.token = token;
        this.intentDirectory = intentDirectory ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "CaseProof", "pending-v1");
        http = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false, UseCookies = false })
        {
            BaseAddress = uri,
            Timeout = TimeSpan.FromSeconds(25)
        };
    }

    internal async Task ConnectAsync(CancellationToken cancellation)
    {
        Catalog = await GetAsync("/api/v1/workspace", cancellation);
        var actor = Catalog.Field("actor");
        var actorId = actor.Text("actor_id");
        var tenant = actor.Text("tenant_id");
        if (actorId.Length == 0 || tenant.Length == 0 || !actor.Field("roles").Items().Any())
            throw new InvalidDataException("서버가 인증된 작업공간 정보를 반환하지 않았습니다.");
        context = Catalog.Text("request_context");
        if (context.Length != 64 || context.Any(c => !Uri.IsHexDigit(c))) context = "";

        var scopeIdentity = JsonSerializer.Serialize(new[] { Endpoint.GetLeftPart(UriPartial.Authority), tenant, actorId });
        scope = SHA256.HashData(Encoding.UTF8.GetBytes(scopeIdentity));
        intentFile = Path.Combine(intentDirectory, Convert.ToHexString(scope) + ".bin");
    }

    internal bool HasRole(string role) => Catalog.Field("actor").Field("roles").Items().Any(value => value.Value() == role);

    internal async Task<JsonElement> GetAsync(string path, CancellationToken cancellation = default) =>
        (await SendAsync(HttpMethod.Get, path, null, null, cancellation)).Body.Field("data");

    internal async Task<IReadOnlyList<JsonElement>> ChangesAsync(Action<int> progress, CancellationToken cancellation)
    {
        var rows = new List<JsonElement>();
        string? cursor = null;
        do
        {
            var path = cursor is null ? QueuePage : QueuePage + "&after=" + Uri.EscapeDataString(cursor);
            var (_, payload) = await SendAsync(HttpMethod.Get, path, null, null, cancellation);
            var previous = cursor;
            var data = payload.Field("data");
            var next = payload.Field("pagination").Field("next_cursor");
            if (data.ValueKind != JsonValueKind.Array || next.ValueKind is not (JsonValueKind.Null or JsonValueKind.String))
                throw new InvalidDataException("서버가 목록의 이어받기 정보를 반환하지 않았습니다.");
            foreach (var row in data.Items())
            {
                var id = row.Text("change_id");
                if (!Guid.TryParseExact(id, "D", out _) || string.CompareOrdinal(id, previous) <= 0)
                    throw new InvalidDataException("요청 목록에 중복 또는 순서 오류가 있습니다.");
                rows.Add(row);
                previous = id;
            }
            cursor = next.GetString();
            if (cursor is not null && (data.GetArrayLength() == 0 || cursor != previous))
                throw new InvalidDataException("서버의 다음 목록 위치가 올바르지 않습니다.");
            progress(rows.Count);
        } while (cursor is not null);
        return rows;
    }

    internal async Task<JsonElement> PreviewCsvAsync(string changeId, int revision, byte[] file, CancellationToken cancellation)
    {
        using var content = new ByteArrayContent(file);
        content.Headers.ContentType = new MediaTypeHeaderValue("text/csv") { CharSet = "utf-8" };
        using var request = CreateRequest(HttpMethod.Post, $"{Changes}/{changeId}/evaluation-runs/preview-csv");
        request.Content = content;
        request.Headers.Add("X-Expected-Revision", revision.ToString(CultureInfo.InvariantCulture));
        if (CanWrite) request.Headers.Add("X-CaseProof-Request-Context", context);
        return (await ReadResponseAsync(request, cancellation)).Body.Field("data");
    }

    internal (bool Exists, bool ContextMatches) Pending()
    {
        var intent = ReadIntent();
        return (intent is not null, intent?.Context == context);
    }

    internal async Task<MutationReceipt> WriteAsync(string path, JsonElement body, int? revision, CancellationToken cancellation)
    {
        using var guard = LockScope();
        if (ReadIntent() is not null) throw new InvalidOperationException("원래 요청을 확인한 뒤 새 결정을 기록하세요.");
        var intent = new RequestIntent(Guid.NewGuid().ToString("D"), path, body.GetRawText(), revision, context);
        SaveIntent(intent);
        return await DispatchAsync(intent, true, cancellation);
    }

    internal async Task<MutationReceipt> RecoverAsync(CancellationToken cancellation)
    {
        using var guard = LockScope();
        var intent = ReadIntent() ?? throw new InvalidOperationException("확인할 원래 요청이 없습니다.");
        if (intent.Context != context)
            throw new InvalidOperationException("원래 요청을 보낸 서버 작업공간으로 다시 연결하세요. 복원본에서 기존 요청을 다시 보내지 않습니다.");
        try
        {
            var (_, payload) = await SendAsync(HttpMethod.Get, "/api/v1/mutations/" + Uri.EscapeDataString(intent.Key), null, null, cancellation);
            return Resolve(intent, payload.Number("original_status"), payload);
        }
        catch (WorkspaceException error) when (error.Status == HttpStatusCode.NotFound && error.Code == "NOT_FOUND")
        {
            return await DispatchAsync(intent, false, cancellation);
        }
    }

    private async Task<MutationReceipt> DispatchAsync(RequestIntent intent, bool first, CancellationToken cancellation)
    {
        try
        {
            var (status, payload) = await SendAsync(HttpMethod.Post, intent.Path, intent.Body, intent, cancellation);
            return Resolve(intent, (int)status, payload);
        }
        catch (WorkspaceException error) when (first && (int)error.Status >= 400 && (int)error.Status < 500
            && error.Code is not ("INVALID_RESPONSE" or "REQUEST_CONTEXT_CHANGED"))
        {
            File.Delete(intentFile!);
            throw;
        }
    }

    private MutationReceipt Resolve(RequestIntent intent, int status, JsonElement payload)
    {
        var data = payload.Field("data");
        var id = data.Text("change_id");
        var responseRevision = payload.Number("result_revision");
        var expectedStatus = intent.Path == Changes || intent.Path.EndsWith("/evaluation-runs", StringComparison.Ordinal) ? 201 : 200;
        if (!Guid.TryParseExact(id, "D", out _) || status != expectedStatus || responseRevision != (intent.Revision ?? 0) + 1
            || data.Number("revision") != responseRevision || (intent.Path != Changes && !intent.Path.StartsWith($"{Changes}/{id}/", StringComparison.Ordinal))
            || payload.Field("replayed").ValueKind is not (JsonValueKind.True or JsonValueKind.False))
            throw new InvalidDataException("원래 요청에 대응하는 저장 결과를 확인하지 못했습니다.");

        File.Delete(intentFile!);
        return new MutationReceipt(id, responseRevision, payload.Flag("replayed"));
    }

    private FileStream LockScope()
    {
        if (!CanWrite) throw new InvalidOperationException("원래 요청을 복구할 수 있는 작업공간 컨텍스트가 필요합니다.");
        Directory.CreateDirectory(intentDirectory);
        try { return new FileStream(intentFile! + ".lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None); }
        catch (IOException error) { throw new IOException("같은 작업공간·계정의 요청이 다른 창에서 처리 중입니다.", error); }
    }

    private RequestIntent? ReadIntent()
    {
        if (intentFile is null || scope is null) return null;
        try
        {
            var secret = ProtectedData.Unprotect(File.ReadAllBytes(intentFile), scope, DataProtectionScope.CurrentUser);
            try { return JsonSerializer.Deserialize<RequestIntent>(secret) ?? throw new InvalidDataException("원래 요청 기록이 비어 있습니다."); }
            finally { CryptographicOperations.ZeroMemory(secret); }
        }
        catch (FileNotFoundException) { return null; }
        catch (DirectoryNotFoundException) { return null; }
        catch (CryptographicException error) { throw new IOException("이 Windows 사용자로 원래 요청 기록을 열 수 없습니다.", error); }
        catch (JsonException error) { throw new IOException("원래 요청 기록의 형식을 확인할 수 없습니다.", error); }
    }

    private void SaveIntent(RequestIntent intent)
    {
        var temporary = intentFile! + "." + Guid.NewGuid().ToString("N") + ".tmp";
        var plaintext = JsonSerializer.SerializeToUtf8Bytes(intent);
        try
        {
            var protectedBytes = ProtectedData.Protect(plaintext, scope, DataProtectionScope.CurrentUser);
            using (var file = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                file.Write(protectedBytes);
                file.Flush(true);
            }
            File.Move(temporary, intentFile!);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plaintext);
            File.Delete(temporary);
        }
    }

    private async Task<(HttpStatusCode Status, JsonElement Body)> SendAsync(HttpMethod method, string path, string? body,
        RequestIntent? intent, CancellationToken cancellation)
    {
        using var request = CreateRequest(method, path);
        if (body is not null) request.Content = new StringContent(body, Encoding.UTF8, "application/json");
        if (intent is not null)
        {
            request.Headers.Add("Idempotency-Key", intent.Key);
            request.Headers.Add("X-CaseProof-Request-Context", intent.Context);
            if (intent.Revision is int revision) request.Headers.Add("X-Expected-Revision", revision.ToString(CultureInfo.InvariantCulture));
        }
        return await ReadResponseAsync(request, cancellation);
    }

    private HttpRequestMessage CreateRequest(HttpMethod method, string path)
    {
        if (!path.StartsWith("/api/v1/", StringComparison.Ordinal) || path.Contains('\\'))
            throw new InvalidDataException("작업공간 요청 주소가 유효하지 않습니다.");
        var request = new HttpRequestMessage(method, path);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.CacheControl = new CacheControlHeaderValue { NoStore = true };
        return request;
    }

    private async Task<(HttpStatusCode Status, JsonElement Body)> ReadResponseAsync(HttpRequestMessage request, CancellationToken cancellation)
    {
        using var response = await http.SendAsync(request, cancellation);
        var content = await response.Content.ReadAsStringAsync(cancellation);
        JsonElement payload;
        try
        {
            using var document = JsonDocument.Parse(content);
            payload = document.RootElement.Clone();
        }
        catch (JsonException) when (!response.IsSuccessStatusCode)
        {
            throw new WorkspaceException(response.StatusCode, "INVALID_RESPONSE", $"서버 응답을 읽을 수 없습니다 ({(int)response.StatusCode}).");
        }
        if (!response.IsSuccessStatusCode)
        {
            var error = payload.Field("error");
            throw new WorkspaceException(response.StatusCode, error.Text("code", "INVALID_RESPONSE"),
                error.Text("message", $"작업공간 요청을 처리하지 못했습니다 ({(int)response.StatusCode})."));
        }
        return (response.StatusCode, payload);
    }

    public void Dispose() => http.Dispose();
}
