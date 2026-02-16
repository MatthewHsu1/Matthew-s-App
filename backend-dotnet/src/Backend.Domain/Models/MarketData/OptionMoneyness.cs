namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// Relationship between strike and underlying price.
    /// </summary>
    public enum OptionMoneyness
    {
        ITM = 0,

        ATM = 1,

        OTM = 2
    }
}
