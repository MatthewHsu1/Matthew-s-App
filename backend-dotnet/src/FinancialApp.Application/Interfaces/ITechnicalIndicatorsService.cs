using FinancialApp.Domain.Models.MarketData;

namespace FinancialApp.Application.Interfaces
{
    /// <summary>
    /// Provides technical indicators for a symbol (RSI, MAs, 20-day high/low) for the wheel decision engine.
    /// </summary>
    public interface ITechnicalIndicatorsService
    {
        /// <summary>
        /// Gets technical indicators for the ticker using daily bars.
        /// </summary>
        /// <param name="ticker">Symbol (e.g. AAPL, MSFT).</param>
        /// <param name="asOfDate">Date for which to compute indicators; null = use latest available bar date.</param>
        /// <param name="cancellationToken">Cancellation token.</param>
        /// <returns>Indicators (RSI14, MA50, MA200, 20-day high/low). Values may be null if insufficient data.</returns>
        Task<TechnicalIndicatorsResult> GetIndicatorsAsync(
            string ticker,
            DateTime? asOfDate = null,
            CancellationToken cancellationToken = default);
    }
}
