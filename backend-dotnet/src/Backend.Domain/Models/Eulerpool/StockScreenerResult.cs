namespace Backend.Domain.Models.Eulerpool;

/// <summary>
/// Represents a single stock result from a screener query.
/// </summary>
public class StockScreenerResult
{
    public string Ticker { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public decimal CurrentPrice { get; set; }
    public decimal? PriceEarningsRatio { get; set; }
    public decimal? DividendYield { get; set; }
    public decimal? PriceToBookRatio { get; set; }
    public decimal? MarketCap { get; set; }
    public string? Sector { get; set; }
    public string? Industry { get; set; }
    public DateTime? LastUpdated { get; set; }
}

