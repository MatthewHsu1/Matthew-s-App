using Backend.Domain.Models.Wheel;

namespace Backend.Api.Contracts.Wheel;

/// <summary>
/// API response for a single ticker's wheel state.
/// </summary>
public sealed class WheelStateResponse
{
    /// <summary>
    /// Underlying ticker symbol.
    /// </summary>
    public string Ticker { get; set; } = string.Empty;

    /// <summary>
    /// Whether the account holds shares in this underlying.
    /// </summary>
    public bool HasShares { get; set; }

    /// <summary>
    /// Number of shares owned (non-negative).
    /// </summary>
    public int SharesOwned { get; set; }

    /// <summary>
    /// Cost basis for the shares when HasShares is true.
    /// </summary>
    public decimal? CostBasis { get; set; }

    /// <summary>
    /// Currently open option type (None, Put, or Call).
    /// </summary>
    public ActiveOptionType ActiveOption { get; set; }

    /// <summary>
    /// Strike of the active option when not None.
    /// </summary>
    public decimal? Strike { get; set; }

    /// <summary>
    /// Expiration date of the active option when not None.
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
    /// Optimistic concurrency version.
    /// </summary>
    public long Version { get; set; }
}
