namespace Backend.Domain.Models.Eulerpool;

/// <summary>
/// Represents the response from a stock screener query with pagination support.
/// </summary>
public class StockScreenerResponse
{
    public List<StockScreenerResult> Results { get; set; } = new();
    public int TotalCount { get; set; }
    public int Page { get; set; }
    public int PageSize { get; set; }
}

