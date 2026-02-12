namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// One OHLCV bar (candle). Used for historical series and indicators (RSI, MAs, 20-day high/low).
    /// </summary>
    public class OhlcvBar
    {
        /// <summary>
        /// Trading date for the bar.
        /// </summary>
        public DateTime Date { get; set; }

        /// <summary>
        /// Bar time; optional for intraday (e.g. 5m, 1h).
        /// </summary>
        public TimeOnly? Time { get; set; }

        /// <summary>
        /// Opening price for the period.
        /// </summary>
        public decimal Open { get; set; }

        /// <summary>
        /// Highest price during the period.
        /// </summary>
        public decimal High { get; set; }

        /// <summary>
        /// Lowest price during the period.
        /// </summary>
        public decimal Low { get; set; }

        /// <summary>
        /// Closing price for the period.
        /// </summary>
        public decimal Close { get; set; }

        /// <summary>
        /// Trading volume for the period.
        /// </summary>
        public long Volume { get; set; }
    }
}
