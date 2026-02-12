namespace FinancialApp.Testing.Http;

public sealed class SequenceHttpMessageHandler(IEnumerable<HttpResponseMessage> responses) : HttpMessageHandler
{
    private readonly Queue<HttpResponseMessage> Response = new(responses);

    public int Attempts { get; private set; }

    public List<string> RequestUris { get; } = [];

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        Attempts++;
        RequestUris.Add(request.RequestUri!.ToString());

        if (Response.Count == 0)
            throw new InvalidOperationException("No configured response available.");

        return Task.FromResult(Response.Dequeue());
    }
}
