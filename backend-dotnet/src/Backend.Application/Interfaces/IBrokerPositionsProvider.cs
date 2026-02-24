using Backend.Application.Models.Wheel;

namespace Backend.Application.Interfaces
{
    /// <summary>
    /// Provides a snapshot of broker positions for reconciliation and state management.
    /// </summary>
    public interface IBrokerPositionsProvider
    {
        /// <summary>
        /// Gets a snapshot of current broker positions.
        /// </summary>
        /// <param name="tickers">
        /// Optional set of ticker symbols to include. When <c>null</c>, all positions are returned.
        /// </param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>
        /// A task that completes with a <see cref="BrokerPositionsSnapshot"/> containing positions as of the snapshot time.
        /// </returns>
        Task<BrokerPositionsSnapshot> GetSnapshotAsync(
            IReadOnlyCollection<string>? tickers = null,
            CancellationToken cancellationToken = default);
    }
}
