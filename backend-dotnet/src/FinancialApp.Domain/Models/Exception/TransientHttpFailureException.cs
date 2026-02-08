using System.Net;

namespace FinancialApp.Domain.Models.Exception
{
    public sealed class TransientHttpFailureException(HttpStatusCode statusCode)
        : System.Exception($"Transient HTTP failure: {statusCode}")
    {
        public HttpStatusCode StatusCode { get; } = statusCode;
    }
}
