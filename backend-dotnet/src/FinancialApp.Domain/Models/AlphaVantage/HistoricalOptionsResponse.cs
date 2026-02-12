using System.Text.Json.Serialization;

namespace FinancialApp.Domain.Models.AlphaVantage
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
    }
}
