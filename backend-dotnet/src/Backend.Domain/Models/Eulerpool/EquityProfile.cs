namespace Backend.Domain.Models.Eulerpool;

/// <summary>
/// Represents an equity profile with basic company information and key metrics from Eulerpool API.
/// </summary>
public class EquityProfile
{
    public string Ticker { get; set; } = string.Empty;
    public string ISIN { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string? Sector { get; set; }
    public string? Industry { get; set; }
    public decimal? MarketCap { get; set; }
    public decimal? PriceEarningsRatio { get; set; }
    public decimal? DividendYield { get; set; }
    public decimal? CurrentPrice { get; set; }
    public DateTime? LastUpdated { get; set; }
}

