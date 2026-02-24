namespace Backend.Api.Contracts.Wheel;

/// <summary>
/// API request body for triggering wheel reconciliation.
/// </summary>
public sealed class ReconcileWheelStateRequest
{
    /// <summary>
    /// Optional list of ticker symbols to reconcile. When null or empty, all stored tickers are reconciled.
    /// </summary>
    public IReadOnlyList<string>? Tickers { get; set; }
}
