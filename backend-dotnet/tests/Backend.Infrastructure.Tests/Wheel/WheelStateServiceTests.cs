using Backend.Application.Interfaces;
using Backend.Application.Services;
using Backend.Domain.Models.Wheel;

namespace Backend.Infrastructure.Tests.Wheel;

public class WheelStateServiceTests
{
    [Fact]
    public async Task UpsertAsync_Throws_WhenActiveOptionIsNoneWithOptionFields()
    {
        var service = new WheelStateService(new InMemoryWheelStateRepository());

        var model = new WheelTickerState
        {
            Ticker = new Ticker("AAPL"),
            HasShares = false,
            SharesOwned = 0,
            ActiveOption = ActiveOptionType.None,
            Strike = 190m
        };

        await Assert.ThrowsAsync<ArgumentException>(() => service.UpsertAsync(model));
    }

    private sealed class InMemoryWheelStateRepository : IWheelStateRepository
    {
        public Task<WheelTickerState?> GetByTickerAsync(Ticker ticker, CancellationToken cancellationToken = default)
            => Task.FromResult<WheelTickerState?>(null);

        public Task<IReadOnlyList<Ticker>> ListTickersAsync(CancellationToken cancellationToken = default)
            => Task.FromResult((IReadOnlyList<Ticker>)[]);

        public Task<WheelTickerState> UpsertAsync(WheelTickerState state, CancellationToken cancellationToken = default)
            => Task.FromResult(state);

        public Task AppendEventAsync(WheelEvent wheelEvent, CancellationToken cancellationToken = default)
            => Task.CompletedTask;

        public Task<IReadOnlyList<WheelEvent>> GetEventsAsync(Ticker ticker, CancellationToken cancellationToken = default)
            => Task.FromResult((IReadOnlyList<WheelEvent>)[]);

        public Task<bool> HasReconciledBucketAsync(Ticker ticker, string bucket, CancellationToken cancellationToken = default)
            => Task.FromResult(false);
    }
}
