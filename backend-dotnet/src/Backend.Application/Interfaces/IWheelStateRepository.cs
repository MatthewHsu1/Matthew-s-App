using Backend.Domain.Models.Wheel;

namespace Backend.Application.Interfaces
{
    /// <summary>
    /// Persists and retrieves wheel ticker state and wheel events.
    /// </summary>
    public interface IWheelStateRepository
    {
        /// <summary>
        /// Gets the current wheel state for the given ticker, if it exists.
        /// </summary>
        /// <param name="ticker">The normalized ticker symbol.</param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>The wheel ticker state, or null if none exists.</returns>
        Task<WheelTickerState?> GetByTickerAsync(Ticker ticker, CancellationToken cancellationToken = default);

        /// <summary>
        /// Lists all tickers that have stored wheel state.
        /// </summary>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>Ordered list of ticker symbols.</returns>
        Task<IReadOnlyList<Ticker>> ListTickersAsync(CancellationToken cancellationToken = default);

        /// <summary>
        /// Inserts or updates the wheel state for the ticker; uses optimistic concurrency via version.
        /// </summary>
        /// <param name="state">The state to upsert.</param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>The persisted state (with updated version and timestamps).</returns>
        Task<WheelTickerState> UpsertAsync(WheelTickerState state, CancellationToken cancellationToken = default);

        /// <summary>
        /// Appends a wheel event to the event log for the ticker.
        /// </summary>
        /// <param name="wheelEvent">The event to append.</param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        Task AppendEventAsync(WheelEvent wheelEvent, CancellationToken cancellationToken = default);

        /// <summary>
        /// Gets all wheel events for the given ticker, ordered by occurrence.
        /// </summary>
        /// <param name="ticker">The normalized ticker symbol.</param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>Ordered list of wheel events.</returns>
        Task<IReadOnlyList<WheelEvent>> GetEventsAsync(Ticker ticker, CancellationToken cancellationToken = default);

        /// <summary>
        /// Checks whether a reconciliation event exists for the given ticker and bucket identifier.
        /// </summary>
        /// <param name="ticker">The normalized ticker symbol.</param>
        /// <param name="bucket">The reconciliation bucket identifier (e.g. time bucket).</param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>True if a matching reconciled event exists; otherwise false.</returns>
        Task<bool> HasReconciledBucketAsync(Ticker ticker, string bucket, CancellationToken cancellationToken = default);
    }
}
