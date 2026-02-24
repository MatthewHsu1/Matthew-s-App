using Backend.Application.Interfaces;
using Backend.Domain.Models.Wheel;

namespace Backend.Application.Services
{
    /// <inheritdoc />
    public sealed class WheelStateService(IWheelStateRepository repository) : IWheelStateService
    {
        /// <inheritdoc />
        public Task<WheelTickerState?> GetByTickerAsync(Ticker ticker, CancellationToken cancellationToken = default)
            => repository.GetByTickerAsync(ticker, cancellationToken);

        /// <inheritdoc />
        public async Task<WheelTickerState> UpsertAsync(WheelTickerState state, CancellationToken cancellationToken = default)
        {
            Validate(state);

            var existing = await repository.GetByTickerAsync(state.Ticker, cancellationToken);

            if (existing is null)
            {
                state.Version = 0;
                var created = await repository.UpsertAsync(state, cancellationToken);

                await repository.AppendEventAsync(new WheelEvent
                {
                    Ticker = created.Ticker,
                    EventType = WheelEventType.StateInitialized,
                    OccurredAtUtc = DateTimeOffset.UtcNow,
                    SharesOwnedBefore = 0,
                    SharesOwnedAfter = created.SharesOwned,
                    ActiveOptionBefore = ActiveOptionType.None,
                    ActiveOptionAfter = created.ActiveOption,
                    CostBasisBefore = null,
                    CostBasisAfter = created.CostBasis
                }, cancellationToken);

                return created;
            }

            if (state.Version <= 0)
                state.Version = existing.Version;

            return await repository.UpsertAsync(state, cancellationToken);
        }

        private static void Validate(WheelTickerState state)
        {
            if (state.SharesOwned < 0)
                throw new ArgumentException("SharesOwned cannot be negative.", nameof(state));

            if (state.HasShares && state.SharesOwned <= 0)
                throw new ArgumentException("SharesOwned must be positive when HasShares is true.", nameof(state));

            if (!state.HasShares && state.SharesOwned != 0)
                throw new ArgumentException("SharesOwned must be zero when HasShares is false.", nameof(state));

            if (!state.HasShares && state.CostBasis.HasValue)
                throw new ArgumentException("CostBasis cannot be set when no shares are owned.", nameof(state));

            if (state.ActiveOption == ActiveOptionType.None)
            {
                if (state.Strike.HasValue || state.Expiration.HasValue || state.OpenPremium.HasValue || state.OpenedAtUtc.HasValue)
                    throw new ArgumentException("Option fields must be null when ActiveOption is None.", nameof(state));

                return;
            }

            if (!state.Strike.HasValue || !state.Expiration.HasValue || !state.OpenedAtUtc.HasValue)
                throw new ArgumentException("Strike, expiration, and opened_at are required when an option is active.", nameof(state));
        }
    }
}
