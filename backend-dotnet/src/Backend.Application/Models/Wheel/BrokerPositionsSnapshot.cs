namespace Backend.Application.Models.Wheel
{
    /// <summary>
    /// Snapshot of broker positions at a point in time for reconciliation.
    /// </summary>
    public sealed class BrokerPositionsSnapshot
    {
        /// <summary>
        /// UTC timestamp when the snapshot was taken.
        /// </summary>
        public DateTimeOffset AsOfUtc { get; set; }

        /// <summary>
        /// Per-ticker position snapshots.
        /// </summary>
        public IReadOnlyList<BrokerTickerSnapshot> Tickers { get; set; } = [];
    }
}
