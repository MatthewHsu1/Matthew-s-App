using FinancialApp.Domain.Models.MarketData;

namespace FinancialApp.Domain.Interfaces
{
    /// <summary>
    /// Provider-agnostic market data.
    /// </summary>
    public interface IMarketDataService
    {
        /// <summary>
        /// Fetches current quote for the given ticker.
        /// </summary>
        /// <param name="ticker">Symbol (e.g. AAPL, MSFT).</param>
        /// <param name="cancellationToken">Cancellation token.</param>
        /// <returns>Current quote or null if not available.</returns>
        Task<StockQuote?> GetCurrentPriceAsync(string ticker, CancellationToken cancellationToken = default);

        /// <summary>
        /// Fetches historical OHLCV bars for indicators (RSI, MAs, 20-day high/low).
        /// </summary>
        /// <param name="ticker">Symbol.</param>
        /// <param name="from">Start date (inclusive).</param>
        /// <param name="to">End date (inclusive).</param>
        /// <param name="interval">Bar interval, e.g. "1D", "1W", "1H", "5m". Implementation-dependent.</param>
        /// <param name="cancellationToken">Cancellation token.</param>
        Task<IReadOnlyList<OhlcvBar>> GetHistoricalPricesAsync(
            string ticker,
            DateTime from,
            DateTime to,
            string? interval = "1D",
            CancellationToken cancellationToken = default);

        /// <summary>
        /// Fetches full options chain contracts for the given ticker across expirations and strikes.
        /// </summary>
        /// <param name="ticker">Underlying symbol.</param>
        /// <param name="cancellationToken">Cancellation token.</param>
        /// <returns>Normalized option contracts used for strike/expiration selection.</returns>
        Task<IReadOnlyList<OptionContractSummary>> GetOptionChainAsync(
            string ticker,
            CancellationToken cancellationToken = default);
    }
}
