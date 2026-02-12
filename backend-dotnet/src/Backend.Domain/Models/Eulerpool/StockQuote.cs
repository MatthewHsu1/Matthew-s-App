namespace Backend.Domain.Models.Eulerpool;

/// <summary>
/// Represents current market quote/price data from Eulerpool API.
/// </summary>
public class StockQuote
{
    public string Ticker { get; set; } = string.Empty;
    public decimal Price { get; set; }
    public decimal? PreviousClose { get; set; }
    public decimal? Change { get; set; }
    public decimal? ChangePercent { get; set; }
    public long? Volume { get; set; }
    public DateTime Timestamp { get; set; }
}

