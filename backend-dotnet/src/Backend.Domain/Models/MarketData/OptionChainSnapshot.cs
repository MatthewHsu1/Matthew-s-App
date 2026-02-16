namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// Normalized full option chain for one underlying at a point in time.
    /// </summary>
    public class OptionChainSnapshot
    {
        public string Ticker { get; set; } = string.Empty;

        public decimal UnderlyingPrice { get; set; }

        public DateTime AsOf { get; set; }

        public IReadOnlyList<OptionContractQuote> Contracts { get; set; } = [];
    }
}
