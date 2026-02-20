using System.Text.Json;

namespace Backend.Domain.Models.Wheel
{
    /// <summary>
    /// A recorded wheel strategy event for a ticker (state change, option open/close, reconciliation, etc.).
    /// </summary>
    public sealed class WheelEvent
    {
        /// <summary>
        /// Unique identifier for the event (e.g. database id).
        /// </summary>
        public long Id { get; set; }

        /// <summary>
        /// Underlying ticker symbol.
        /// </summary>
        public Ticker Ticker { get; set; }

        /// <summary>
        /// Type of wheel event.
        /// </summary>
        public WheelEventType EventType { get; set; }

        /// <summary>
        /// UTC timestamp when the event occurred.
        /// </summary>
        public DateTimeOffset OccurredAtUtc { get; set; }

        /// <summary>
        /// Active option type before the event, if applicable.
        /// </summary>
        public ActiveOptionType? ActiveOptionBefore { get; set; }

        /// <summary>
        /// Active option type after the event, if applicable.
        /// </summary>
        public ActiveOptionType? ActiveOptionAfter { get; set; }

        /// <summary>
        /// Shares owned before the event, if applicable.
        /// </summary>
        public int? SharesOwnedBefore { get; set; }

        /// <summary>
        /// Shares owned after the event, if applicable.
        /// </summary>
        public int? SharesOwnedAfter { get; set; }

        /// <summary>
        /// Cost basis before the event, if applicable.
        /// </summary>
        public decimal? CostBasisBefore { get; set; }

        /// <summary>
        /// Cost basis after the event, if applicable.
        /// </summary>
        public decimal? CostBasisAfter { get; set; }

        /// <summary>
        /// Reason the option was closed (expired, assigned, etc.), when applicable.
        /// </summary>
        public OptionCloseReason? CloseReason { get; set; }

        /// <summary>
        /// Optional JSON metadata (e.g. reconciliation bucket).
        /// </summary>
        public JsonDocument? MetadataJson { get; set; }
    }
}
