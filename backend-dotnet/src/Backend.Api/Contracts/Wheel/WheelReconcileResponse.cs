namespace Backend.Api.Contracts.Wheel;

/// <summary>
/// API response for a wheel reconcile request.
/// </summary>
public sealed class WheelReconcileResponse
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
    /// Total number of wheel events appended.
    /// </summary>
    public int EventsAppended { get; set; }
}
