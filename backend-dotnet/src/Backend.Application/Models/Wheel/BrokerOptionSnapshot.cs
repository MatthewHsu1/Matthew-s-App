namespace Backend.Application.Models.Wheel
{
    /// <summary>
    /// Snapshot of a single option position from the broker (put or call).
    /// </summary>
    public sealed class BrokerOptionSnapshot
    {
        /// <summary>
        /// Option ticker/symbol.
        /// </summary>
        public string Ticker { get; set; } = string.Empty;

        /// <summary>
        /// Whether this is a put or call.
        /// </summary>
        public Backend.Domain.Models.Wheel.ActiveOptionType Type { get; set; }

        /// <summary>
        /// Strike price.
        /// </summary>
        public decimal Strike { get; set; }

        /// <summary>
        /// Expiration date.
        /// </summary>
        public DateOnly Expiration { get; set; }
    }
}
