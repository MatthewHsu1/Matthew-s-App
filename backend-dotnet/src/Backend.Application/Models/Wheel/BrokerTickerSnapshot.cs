namespace Backend.Application.Models.Wheel
{
    /// <summary>
    /// Snapshot of a single ticker's positions from the broker (shares and optional open option).
    /// </summary>
    public sealed class BrokerTickerSnapshot
    {
        /// <summary>
        /// Underlying ticker symbol.
        /// </summary>
        public string Ticker { get; set; } = string.Empty;

        /// <summary>
        /// Number of shares owned (non-negative).
        /// </summary>
        public int SharesOwned { get; set; }

        /// <summary>
        /// Cost basis for the shares, if applicable.
        /// </summary>
        public decimal? CostBasis { get; set; }

        /// <summary>
        /// Open option position (put or call), if any.
        /// </summary>
        public BrokerOptionSnapshot? OpenOption { get; set; }
    }
}
