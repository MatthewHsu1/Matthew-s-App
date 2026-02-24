using Backend.Domain.Models.Wheel;

namespace Backend.Api.Contracts.Wheel;

/// <summary>
/// API request body for creating or updating wheel state for a ticker.
/// </summary>
public sealed class UpsertWheelStateRequest
{
    /// <summary>
    /// Whether the account holds shares in this underlying.
    /// </summary>
    public bool HasShares { get; set; }

    /// <summary>
    /// Number of shares owned (non-negative; must be zero when HasShares is false).
    /// </summary>
    public int SharesOwned { get; set; }

    /// <summary>
    /// Cost basis for the shares when HasShares is true; otherwise ignored.
    /// </summary>
    public decimal? CostBasis { get; set; }

    /// <summary>
    /// Currently open option type (None, Put, or Call).
    /// </summary>
    public ActiveOptionType ActiveOption { get; set; }

    /// <summary>
    /// Strike of the active option when ActiveOption is not None.
    /// </summary>
    public decimal? Strike { get; set; }

    /// <summary>
    /// Expiration date of the active option when ActiveOption is not None.
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
    /// Optional version for optimistic concurrency; required when updating an existing state.
    /// </summary>
    public long? Version { get; set; }
}
