namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// Provider-agnostic current price/quote. Used by wheel and indicators; infrastructure maps provider responses to this.
    /// </summary>
    public class StockQuote
    {
        /// <summary>
        /// Stock or instrument symbol (e.g. AAPL, MSFT).
        /// </summary>
        public string Ticker { get; set; } = string.Empty;

        /// <summary>
        /// Current last/close price.
        /// </summary>
        public decimal Price { get; set; }

        /// <summary>
        /// Previous trading session's closing price, when available.
        /// </summary>
        public decimal? PreviousClose { get; set; }

        /// <summary>
        /// Absolute price change from previous close.
        /// </summary>
        public decimal? Change { get; set; }

        /// <summary>
        /// Percentage change from previous close.
        /// </summary>
        public decimal? ChangePercent { get; set; }

        /// <summary>
        /// Trading volume for the period, when available.
        /// </summary>
        public long? Volume { get; set; }

        /// <summary>
        /// Time the quote/price was observed or reported.
        /// </summary>
        public DateTime Timestamp { get; set; }
    }
}
