using Backend.Domain.Interfaces;
using Backend.Domain.Models.MarketData;
using Skender.Stock.Indicators;

namespace Backend.Infrastructure.Services.Indicators
{
    internal sealed class SkenderTechnicalIndicatorCalculator : ITechnicalIndicatorCalculator
    {
        private const int RsiPeriod = 14;
        private const int Ma50Period = 50;
        private const int Ma200Period = 200;
        private const int TwentyDayPeriod = 20;

        public decimal? ComputeRsi14(IReadOnlyList<OhlcvBar> bars)
        {
            if (bars is null || bars.Count < RsiPeriod + 1)
                return null;

            var rsi = ToIndicatorQuotes(bars)
                .GetRsi(RsiPeriod)
                .LastOrDefault()?.Rsi;

            return ToDecimal(rsi);
        }

        public (decimal? Ma50, decimal? Ma200) ComputeMovingAverages(IReadOnlyList<OhlcvBar> bars)
        {
            if (bars is null || bars.Count == 0)
                return (null, null);

            decimal? ma50 = null;
            decimal? ma200 = null;
            var quotes = ToIndicatorQuotes(bars);

            if (bars.Count >= Ma50Period)
            {
                var result = quotes.GetSma(Ma50Period).LastOrDefault()?.Sma;
                ma50 = ToDecimal(result);
            }

            if (bars.Count >= Ma200Period)
            {
                var result = quotes.GetSma(Ma200Period).LastOrDefault()?.Sma;
                ma200 = ToDecimal(result);
            }

            return (ma50, ma200);
        }

        public (decimal? TwentyDayHigh, decimal? TwentyDayLow) ComputeTwentyDayHighLow(IReadOnlyList<OhlcvBar> bars)
        {
            if (bars is null || bars.Count < TwentyDayPeriod)
                return (null, null);

            var window = bars.Skip(bars.Count - TwentyDayPeriod);
            return (window.Max(b => b.High), window.Min(b => b.Low));
        }

        private static decimal? ToDecimal(double? value)
            => value.HasValue ? Convert.ToDecimal(value.Value) : null;

        private static List<Quote> ToIndicatorQuotes(IEnumerable<OhlcvBar> bars)
            => bars.Select(b => new Quote
            {
                Date = b.Date,
                Open = b.Open,
                High = b.High,
                Low = b.Low,
                Close = b.Close,
                Volume = b.Volume
            }).ToList();
    }
}
