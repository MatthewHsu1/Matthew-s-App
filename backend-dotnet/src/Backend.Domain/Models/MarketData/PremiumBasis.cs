namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// Premium field basis used for contract ranking/selection.
    /// </summary>
    public enum PremiumBasis
    {
        Mid = 0,

        Bid = 1,

        Ask = 2,

        Last = 3
    }
}
