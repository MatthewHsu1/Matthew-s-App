using Backend.Domain.Models.Wheel;

namespace Backend.Application.Interfaces
{
    /// <summary>
    /// Application service for reading and updating wheel ticker state (with validation and event emission).
    /// </summary>
    public interface IWheelStateService
    {
        /// <summary>
        /// Gets the current wheel state for the given ticker, if it exists.
        /// </summary>
        /// <param name="ticker">The normalized ticker symbol.</param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>The wheel ticker state, or null if none exists.</returns>
        Task<WheelTickerState?> GetByTickerAsync(Ticker ticker, CancellationToken cancellationToken = default);

        /// <summary>
        /// Inserts or updates wheel state for the ticker; validates input and appends state-initialized event when creating.
        /// </summary>
        /// <param name="state">The state to upsert.</param>
        /// <param name="cancellationToken">Cancellation token for the operation.</param>
        /// <returns>The persisted state (with updated version and timestamps).</returns>
        Task<WheelTickerState> UpsertAsync(WheelTickerState state, CancellationToken cancellationToken = default);
    }
}
