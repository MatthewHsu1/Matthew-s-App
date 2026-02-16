namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// Normalized option contract with pricing/greeks/moneyness for Wheel selection.
    /// </summary>
    public class OptionContractQuote
    {
        public string Symbol { get; set; } = string.Empty;

        public OptionContractType Type { get; set; }

        public decimal Strike { get; set; }

        public DateOnly Expiration { get; set; }

        public decimal? Bid { get; set; }

        public decimal? Ask { get; set; }

        public decimal? Last { get; set; }

        public decimal? Mid { get; set; }

        public decimal? SelectedPremium { get; set; }

        public PremiumBasis? SelectedPremiumBasis { get; set; }

        public decimal? ImpliedVolatility { get; set; }

        public OptionGreeks? Greeks { get; set; }

        public OptionMoneyness Moneyness { get; set; }

        public bool HasCompleteGreeks { get; set; }

        public string? SelectionEligibilityReason { get; set; }
    }
}
