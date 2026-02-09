using FinancialApp.Application.Interfaces;
using FinancialApp.Domain.Interfaces;
using FinancialApp.Domain.Models.MarketData;
using FinancialApp.Domain.Services;

namespace FinancialApp.Application.Services
{
    public sealed class TechnicalIndicatorsService(IMarketDataService marketDataService)
        : ITechnicalIndicatorsService
    {
        /// <summary>
        /// Calendar days to request so we get at least 200 trading days for MA200.
        /// </summary>
        private const int LookbackCalendarDays = 300;

        public async Task<TechnicalIndicatorsResult> GetIndicatorsAsync(
            string ticker,
            DateTime? asOfDate = null,
            CancellationToken cancellationToken = default)
        {
            var to = asOfDate?.Date ?? DateTime.UtcNow.Date;
            var from = to.AddDays(-LookbackCalendarDays);

            var bars = await marketDataService
                .GetHistoricalPricesAsync(ticker, from, to, "1D", cancellationToken)
                .ConfigureAwait(false);

            if (bars is null || bars.Count == 0)
                return new TechnicalIndicatorsResult { Ticker = ticker, AsOfDate = to };

            // Ascending by date (oldest first)
            var ordered = bars.OrderBy(b => b.Date).ToList();

            // Restrict to on-or-before asOfDate so indicators are as of that day
            if (asOfDate.HasValue)
            {
                var cutoff = asOfDate.Value.Date;
                ordered = [.. ordered.Where(b => b.Date <= cutoff)];

                if (ordered.Count == 0)
                    return new TechnicalIndicatorsResult { Ticker = ticker, AsOfDate = to };
            }

            var asOf = ordered[^1].Date;

            var rsi14 = TechnicalIndicatorCalculator.ComputeRsi14(ordered);
            var (ma50, ma200) = TechnicalIndicatorCalculator.ComputeMovingAverages(ordered);
            var (twentyDayHigh, twentyDayLow) = TechnicalIndicatorCalculator.ComputeTwentyDayHighLow(ordered);

            return new TechnicalIndicatorsResult
            {
                Ticker = ticker,
                AsOfDate = asOf,
                Rsi14 = rsi14,
                Ma50 = ma50,
                Ma200 = ma200,
                TwentyDayHigh = twentyDayHigh,
                TwentyDayLow = twentyDayLow
            };
        }
    }
}
