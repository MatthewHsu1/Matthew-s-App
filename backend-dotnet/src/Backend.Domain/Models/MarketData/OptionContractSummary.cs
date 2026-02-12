namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// Normalized option contract identity for contract selection.
    /// </summary>
    public class OptionContractSummary
    {
        /// <summary>
        /// Provider contract symbol/identifier (e.g. AAPL250117C00190000).
        /// </summary>
        public string Symbol { get; set; } = string.Empty;

        /// <summary>
        /// Call or put type.
        /// </summary>
        public OptionContractType Type { get; set; }

        /// <summary>
        /// Contract strike price.
        /// </summary>
        public decimal Strike { get; set; }

        /// <summary>
        /// Contract expiration date.
        /// </summary>
        public DateOnly Expiration { get; set; }
    }
}
