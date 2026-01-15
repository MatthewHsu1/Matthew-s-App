using FinancialApp.Domain.Models.Eulerpool;

namespace FinancialApp.Domain.Extensions.Eulerpool;

/// <summary>
/// Extension methods for StockFundamentals.
/// </summary>
public static class StockFundamentalsExtensions
{
    /// <summary>
    /// Calculates Price-to-Book ratio if not directly provided.
    /// </summary>
    /// <param name="fundamentals">The stock fundamentals instance</param>
    /// <param name="currentPrice">Current stock price</param>
    /// <returns>Price-to-Book ratio or null if insufficient data</returns>
    public static decimal? CalculatePriceToBookRatio(this StockFundamentals fundamentals, decimal? currentPrice)
    {
        if (fundamentals.PriceToBookRatio.HasValue)
            return fundamentals.PriceToBookRatio;
            
        if (currentPrice.HasValue && fundamentals.BookValuePerShare.HasValue && fundamentals.BookValuePerShare.Value > 0)
            return currentPrice.Value / fundamentals.BookValuePerShare.Value;
            
        return null;
    }
}

