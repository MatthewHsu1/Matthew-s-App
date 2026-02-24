namespace Backend.Application.Models.Wheel
{
    /// <summary>
    /// Result of a wheel reconciliation run.
    /// </summary>
    public sealed class WheelReconciliationResult
    {
        /// <summary>
        /// Number of tickers considered for reconciliation.
        /// </summary>
        public int ProcessedTickers { get; set; }

        /// <summary>
        /// Number of tickers whose state or events were updated.
        /// </summary>
        public int UpdatedTickers { get; set; }

        /// <summary>
        /// Total number of wheel events appended during this run.
        /// </summary>
        public int EventsAppended { get; set; }
    }
}
