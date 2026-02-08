using System.Text.Json.Serialization;

namespace FinancialApp.Domain.Models.AlphaVantage
{
    public sealed class GlobalQuoteResponse
    {
        [JsonPropertyName("Global Quote")]
        public GlobalQuoteDto? GlobalQuote { get; set; }
    }
}
