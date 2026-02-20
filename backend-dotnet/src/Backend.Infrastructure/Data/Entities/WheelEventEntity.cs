using Backend.Domain.Models.Wheel;
using System.Text.Json;

namespace Backend.Infrastructure.Data.Entities
{
    /// <summary>
    /// EF Core entity for a wheel event stored in the database.
    /// </summary>
    public sealed class WheelEventEntity
    {
        /// <summary>
        /// Primary key (database-generated).
        /// </summary>
        public long Id { get; set; }

        /// <summary>
        /// Underlying ticker symbol (normalized).
        /// </summary>
        public string Ticker { get; set; } = string.Empty;

        /// <summary>
        /// Type of wheel event.
        /// </summary>
        public WheelEventType EventType { get; set; }

        /// <summary>
        /// UTC timestamp when the event occurred.
        /// </summary>
        public DateTimeOffset OccurredAtUtc { get; set; }

        /// <summary>
        /// Active option type before the event.
        /// </summary>
        public ActiveOptionType? ActiveOptionBefore { get; set; }

        /// <summary>
        /// Active option type after the event.
        /// </summary>
        public ActiveOptionType? ActiveOptionAfter { get; set; }

        /// <summary>
        /// Shares owned before the event.
        /// </summary>
        public int? SharesOwnedBefore { get; set; }

        /// <summary>
        /// Shares owned after the event.
        /// </summary>
        public int? SharesOwnedAfter { get; set; }

        /// <summary>
        /// Cost basis before the event.
        /// </summary>
        public decimal? CostBasisBefore { get; set; }

        /// <summary>
        /// Cost basis after the event.
        /// </summary>
        public decimal? CostBasisAfter { get; set; }

        /// <summary>
        /// Reason the option was closed, when applicable.
        /// </summary>
        public OptionCloseReason? CloseReason { get; set; }

        /// <summary>
        /// Optional JSON metadata (stored as jsonb).
        /// </summary>
        public JsonDocument? MetadataJson { get; set; }
    }
}
