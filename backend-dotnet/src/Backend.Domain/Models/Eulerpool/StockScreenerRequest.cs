namespace Backend.Domain.Models.Eulerpool;

/// <summary>
/// Represents filtering criteria for stock screening using Eulerpool API.
/// </summary>
public class StockScreenerRequest
{
    public decimal? MaxPriceEarningsRatio { get; set; }
    public decimal? MinPriceEarningsRatio { get; set; }
    public decimal? MinDividendYield { get; set; }
    public decimal? MaxDividendYield { get; set; }
    public decimal? MaxPriceToBookRatio { get; set; }
    public decimal? MinPriceToBookRatio { get; set; }
    public string? Sector { get; set; }
    public string? Exchange { get; set; }
    public decimal? MinMarketCap { get; set; }
    public decimal? MaxMarketCap { get; set; }
    public int? Limit { get; set; }
    public int? Offset { get; set; }
}

