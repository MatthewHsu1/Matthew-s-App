using Backend.Application.Models.Wheel;
using Backend.Domain.Models.Wheel;

namespace Backend.Application.Interfaces
{
    /// <summary>
    /// Reconciles wheel state with broker positions and records reconciliation events.
    /// </summary>
    public interface IWheelReconciliationService
    {
        /// <summary>
        /// Runs reconciliation for the given tickers (or all known tickers when <paramref name="tickers"/> is null or empty).
        /// </summary>
        /// <param name="tickers">Optional set of ticker symbols to reconcile. When null or empty, all stored tickers are reconciled.</param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>A task that completes with a <see cref="WheelReconciliationResult"/> summarizing processed and updated tickers and events appended.</returns>
        Task<WheelReconciliationResult> ReconcileAsync(
            IReadOnlyCollection<Ticker>? tickers = null,
            CancellationToken cancellationToken = default);
    }
}
