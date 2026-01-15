using FinancialApp.Domain.Models.Eulerpool;

namespace FinancialApp.Domain.Extensions.Eulerpool;

/// <summary>
/// Extension methods for StockScreenerRequest.
/// </summary>
public static class StockScreenerRequestExtensions
{
    /// <summary>
    /// Validates that the request has at least one filter criteria.
    /// </summary>
    /// <param name="request">The stock screener request instance</param>
    /// <returns>True if at least one filter is specified, otherwise false</returns>
    public static bool HasFilters(this StockScreenerRequest request)
    {
        return request.MaxPriceEarningsRatio.HasValue ||
               request.MinPriceEarningsRatio.HasValue ||
               request.MinDividendYield.HasValue ||
               request.MaxDividendYield.HasValue ||
               request.MaxPriceToBookRatio.HasValue ||
               request.MinPriceToBookRatio.HasValue ||
               !string.IsNullOrWhiteSpace(request.Sector) ||
               !string.IsNullOrWhiteSpace(request.Exchange) ||
               request.MinMarketCap.HasValue ||
               request.MaxMarketCap.HasValue;
    }
}

