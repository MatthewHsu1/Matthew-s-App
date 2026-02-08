using System.Text.Json.Serialization;

namespace FinancialApp.Domain.Models.AlphaVantage
{
    public sealed class TimeSeriesDailyResponse
    {
        [JsonPropertyName("Time Series (Daily)")]
        public Dictionary<string, DailyBarDto>? TimeSeriesDaily { get; set; }
    }
}
