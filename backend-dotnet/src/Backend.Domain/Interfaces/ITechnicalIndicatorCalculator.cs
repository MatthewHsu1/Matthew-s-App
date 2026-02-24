using Backend.Domain.Models.MarketData;

namespace Backend.Domain.Interfaces
{
    /// <summary>
    /// Provider-agnostic technical indicator calculations for OHLCV bars.
    /// </summary>
    public interface ITechnicalIndicatorCalculator
    {
        decimal? ComputeRsi14(IReadOnlyList<OhlcvBar> bars);

        (decimal? Ma50, decimal? Ma200) ComputeMovingAverages(IReadOnlyList<OhlcvBar> bars);

        (decimal? TwentyDayHigh, decimal? TwentyDayLow) ComputeTwentyDayHighLow(IReadOnlyList<OhlcvBar> bars);
    }
}
