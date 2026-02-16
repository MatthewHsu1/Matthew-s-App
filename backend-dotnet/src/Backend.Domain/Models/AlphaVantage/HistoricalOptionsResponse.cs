using System.Text.Json.Serialization;

namespace Backend.Domain.Models.AlphaVantage
{
    public sealed class HistoricalOptionsResponse
    {
        [JsonPropertyName("endpoint")]
        public string? Endpoint { get; set; }

        [JsonPropertyName("message")]
        public string? Message { get; set; }

        [JsonPropertyName("data")]
        public List<HistoricalOptionsContractDto>? Data { get; set; }
    }

    public sealed class HistoricalOptionsContractDto
    {
        [JsonPropertyName("contractID")]
        public string? ContractId { get; set; }

        [JsonPropertyName("type")]
        public string? Type { get; set; }

        [JsonPropertyName("strike")]
        public string? Strike { get; set; }

        [JsonPropertyName("expiration")]
        public string? Expiration { get; set; }

        [JsonPropertyName("bid")]
        public string? Bid { get; set; }

        [JsonPropertyName("ask")]
        public string? Ask { get; set; }

        [JsonPropertyName("last")]
        public string? Last { get; set; }

        [JsonPropertyName("implied_volatility")]
        public string? ImpliedVolatility { get; set; }

        [JsonPropertyName("delta")]
        public string? Delta { get; set; }

        [JsonPropertyName("gamma")]
        public string? Gamma { get; set; }

        [JsonPropertyName("theta")]
        public string? Theta { get; set; }

        [JsonPropertyName("vega")]
        public string? Vega { get; set; }
    }
}
