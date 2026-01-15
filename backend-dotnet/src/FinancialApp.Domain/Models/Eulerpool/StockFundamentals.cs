namespace FinancialApp.Domain.Models.Eulerpool;

/// <summary>
/// Represents detailed financial fundamentals from Eulerpool API including income statement,
/// balance sheet metrics, and derived valuation ratios.
/// </summary>
public class StockFundamentals
{
    public string Ticker { get; set; } = string.Empty;
    public string ISIN { get; set; } = string.Empty;
    public DateTime? ReportDate { get; set; }
    
    // Income Statement Metrics
    public decimal? EarningsPerShare { get; set; }
    public decimal? Revenue { get; set; }
    public decimal? NetIncome { get; set; }
    
    // Balance Sheet Metrics (for P/B calculation)
    public decimal? BookValuePerShare { get; set; }
    public decimal? TotalEquity { get; set; }
    public decimal? SharesOutstanding { get; set; }
    
    // Valuation Ratios
    public decimal? PriceEarningsRatio { get; set; }
    public decimal? PriceToBookRatio { get; set; }
    public decimal? PriceToSalesRatio { get; set; }
    
    // Dividend Metrics
    public decimal? DividendYield { get; set; }
    public decimal? DividendPerShare { get; set; }
    public decimal? DividendPayoutRatio { get; set; }
}

