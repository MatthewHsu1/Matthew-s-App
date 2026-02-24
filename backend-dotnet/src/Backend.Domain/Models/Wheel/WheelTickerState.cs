namespace Backend.Domain.Models.Wheel
{
    /// <summary>
    /// Current wheel strategy state for a single ticker (shares, cost basis, active option).
    /// </summary>
    public sealed class WheelTickerState
    {
        /// <summary>
        /// Underlying ticker symbol (normalized).
        /// </summary>
        public Ticker Ticker { get; set; }

        /// <summary>
        /// Whether the account holds shares in this underlying.
        /// </summary>
        public bool HasShares { get; set; }

        /// <summary>
        /// Number of shares owned (non-negative; must match HasShares).
        /// </summary>
        public int SharesOwned { get; set; }

        /// <summary>
        /// Cost basis for the shares when HasShares is true; otherwise null.
        /// </summary>
        public decimal? CostBasis { get; set; }

        /// <summary>
        /// Currently open option type (None, Put, or Call).
        /// </summary>
        public ActiveOptionType ActiveOption { get; set; } = ActiveOptionType.None;

        /// <summary>
        /// Strike of the active option, when ActiveOption is not None.
        /// </summary>
        public decimal? Strike { get; set; }

        /// <summary>
        /// Expiration date of the active option, when ActiveOption is not None.
        /// </summary>
        public DateOnly? Expiration { get; set; }

        /// <summary>
        /// Premium received when the active option was opened.
        /// </summary>
        public decimal? OpenPremium { get; set; }

        /// <summary>
        /// UTC timestamp when the active option was opened.
        /// </summary>
        public DateTimeOffset? OpenedAtUtc { get; set; }

        /// <summary>
        /// UTC timestamp when this state was last updated.
        /// </summary>
        public DateTimeOffset UpdatedAtUtc { get; set; }

        /// <summary>
        /// Optimistic concurrency version; incremented on each update.
        /// </summary>
        public long Version { get; set; }
    }
}
