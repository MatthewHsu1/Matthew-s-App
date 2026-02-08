using System.Text.Json.Serialization;

namespace FinancialApp.Domain.Models.AlphaVantage
{
    public sealed class GlobalQuoteDto
    {
        [JsonPropertyName("01. symbol")]
        public string? Symbol { get; set; }

        [JsonPropertyName("05. price")]
        public string? Price { get; set; }

        [JsonPropertyName("06. volume")]
        public string? Volume { get; set; }

        [JsonPropertyName("07. latest trading day")]
        public string? LatestTradingDay { get; set; }

        [JsonPropertyName("08. previous close")]
        public string? PreviousClose { get; set; }

        [JsonPropertyName("09. change")]
        public string? Change { get; set; }

        [JsonPropertyName("10. change percent")]
        public string? ChangePercent { get; set; }
    }
}
