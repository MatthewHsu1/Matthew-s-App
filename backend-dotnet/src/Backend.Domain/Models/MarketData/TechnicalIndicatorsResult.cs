namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// Technical indicators for a symbol at a point in time (for wheel decision engine).
    /// </summary>
    public class TechnicalIndicatorsResult
    {
        /// <summary>
        /// The ticker symbol of the stock.
        /// </summary>
        public string Ticker { get; set; } = "";

        /// <summary>
        /// The date and time of the indicators.
        /// </summary>
        public DateTime AsOfDate { get; set; }

        /// <summary>
        /// RSI(14), 0–100. Null if insufficient data.
        /// </summary>
        public decimal? Rsi14 { get; set; }

        /// <summary>
        /// SMA(50) of close. Null if &lt; 50 bars.
        /// </summary>
        public decimal? Ma50 { get; set; }

        /// <summary>
        /// SMA(200) of close. Null if &lt; 200 bars.
        /// </summary>
        public decimal? Ma200 { get; set; }

        /// <summary>
        /// Max(High) over last 20 trading days. Null if &lt; 20 bars.
        /// </summary>
        public decimal? TwentyDayHigh { get; set; }

        /// <summary>
        /// Min(Low) over last 20 trading days. Null if &lt; 20 bars.
        /// </summary>
        public decimal? TwentyDayLow { get; set; }
    }
}
