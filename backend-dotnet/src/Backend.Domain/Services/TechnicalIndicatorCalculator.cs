using Backend.Domain.Models.MarketData;

namespace Backend.Domain.Services
{
    /// <summary>
    /// Pure technical indicator calculations. Input bars must be ascending by date (oldest first).
    /// </summary>
    public static class TechnicalIndicatorCalculator
    {
        private const int RsiPeriod = 14;
        private const int Ma50Period = 50;
        private const int Ma200Period = 200;
        private const int TwentyDayPeriod = 20;

        /// <summary>
        /// Computes RSI(14) using Wilder smoothing. Requires at least 15 bars (ascending by date).
        /// </summary>
        public static decimal? ComputeRsi14(IReadOnlyList<OhlcvBar> bars)
        {
            if (bars is null || bars.Count < RsiPeriod + 1)
                return null;

            decimal avgGain = 0;
            decimal avgLoss = 0;

            // First average: simple 14-period average of gains and losses (over first 14 changes)
            for (int i = 1; i <= RsiPeriod; i++)
            {
                var prevClose = bars[i - 1].Close;
                var close = bars[i].Close;
                avgGain += Math.Max(close - prevClose, 0);
                avgLoss += Math.Max(prevClose - close, 0);
            }
            avgGain /= RsiPeriod;
            avgLoss /= RsiPeriod;

            // Smoothed RSI for remaining bars
            for (int i = RsiPeriod + 1; i < bars.Count; i++)
            {
                var prevClose = bars[i - 1].Close;
                var close = bars[i].Close;
                var gain = Math.Max(close - prevClose, 0);
                var loss = Math.Max(prevClose - close, 0);

                avgGain = (avgGain * (RsiPeriod - 1) + gain) / RsiPeriod;
                avgLoss = (avgLoss * (RsiPeriod - 1) + loss) / RsiPeriod;
            }

            if (avgLoss == 0)
                return 100m;

            var rs = avgGain / avgLoss;
            return 100m - (100m / (1 + rs));
        }

        /// <summary>
        /// Computes latest SMA(50) and SMA(200) from close prices. Requires 50 and 200 bars respectively.
        /// </summary>
        public static (decimal? Ma50, decimal? Ma200) ComputeMovingAverages(IReadOnlyList<OhlcvBar> bars)
        {
            if (bars is null || bars.Count == 0)
                return (null, null);

            decimal? ma50 = null;
            decimal? ma200 = null;

            if (bars.Count >= Ma50Period)
            {
                decimal sum50 = 0;
                for (int i = bars.Count - Ma50Period; i < bars.Count; i++)
                    sum50 += bars[i].Close;
                ma50 = sum50 / Ma50Period;
            }

            if (bars.Count >= Ma200Period)
            {
                decimal sum200 = 0;
                for (int i = bars.Count - Ma200Period; i < bars.Count; i++)
                    sum200 += bars[i].Close;
                ma200 = sum200 / Ma200Period;
            }

            return (ma50, ma200);
        }

        /// <summary>
        /// 20-day high = max(High), 20-day low = min(Low) over the last 20 bars (support/resistance proxy).
        /// </summary>
        public static (decimal? TwentyDayHigh, decimal? TwentyDayLow) ComputeTwentyDayHighLow(IReadOnlyList<OhlcvBar> bars)
        {
            if (bars is null || bars.Count < TwentyDayPeriod)
                return (null, null);

            var window = bars.Skip(bars.Count - TwentyDayPeriod).ToList();
            var high = window.Max(b => b.High);
            var low = window.Min(b => b.Low);
            return (high, low);
        }
    }
}
