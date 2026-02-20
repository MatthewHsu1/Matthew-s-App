using Backend.Application.Interfaces;
using Backend.Application.Models.Wheel;
using Backend.Application.Services;
using Backend.Domain.Models.Wheel;
using System.Text.Json;

namespace Backend.Infrastructure.Tests.Wheel;

public class WheelReconciliationServiceTests
{
    [Fact]
    public async Task HasReconciledBucketAsync_ReturnsFalse_WhenBucketDoesNotMatch()
    {
        var repository = new InMemoryWheelStateRepository();
        repository.Events.Add(new WheelEvent
        {
            Ticker = new Ticker("MSFT"),
            EventType = WheelEventType.Reconciled,
            OccurredAtUtc = DateTimeOffset.UtcNow,
            MetadataJson = JsonDocument.Parse("{\"bucket\":\"2026021913\"}")
        });

        var hasBucket = await repository.HasReconciledBucketAsync(new Ticker("MSFT"), "2026021914");

        Assert.False(hasBucket);
    }

    [Fact]
    public async Task ReconcileAsync_ClosesExpiredOption_WhenMissingFromBroker()
    {
        var repository = new InMemoryWheelStateRepository();
        var state = await repository.UpsertAsync(new WheelTickerState
        {
            Ticker = new Ticker("AAPL"),
            HasShares = false,
            SharesOwned = 0,
            ActiveOption = ActiveOptionType.Put,
            Strike = 170m,
            Expiration = DateOnly.FromDateTime(DateTime.UtcNow.Date.AddDays(-1)),
            OpenedAtUtc = DateTimeOffset.UtcNow.AddDays(-10)
        });

        var provider = new FakeBrokerPositionsProvider(new BrokerPositionsSnapshot
        {
            AsOfUtc = DateTimeOffset.UtcNow,
            Tickers =
            [
                new BrokerTickerSnapshot
                {
                    Ticker = "AAPL",
                    SharesOwned = 0,
                    CostBasis = null,
                    OpenOption = null
                }
            ]
        });

        var service = new WheelReconciliationService(repository, provider);

        var result = await service.ReconcileAsync();
        var updated = await repository.GetByTickerAsync(new Ticker("AAPL"));

        Assert.NotNull(updated);
        Assert.Equal(1, result.UpdatedTickers);
        Assert.Equal(ActiveOptionType.None, updated!.ActiveOption);
        Assert.Null(updated.Strike);
        Assert.Contains(repository.Events, e => e.EventType == WheelEventType.Expired);
    }

    [Fact]
    public async Task ReconcileAsync_IsIdempotent_ByBucket()
    {
        var asOf = new DateTimeOffset(2026, 2, 19, 13, 10, 0, TimeSpan.Zero);

        var repository = new InMemoryWheelStateRepository();
        await repository.UpsertAsync(new WheelTickerState
        {
            Ticker = new Ticker("MSFT"),
            HasShares = false,
            SharesOwned = 0,
            ActiveOption = ActiveOptionType.Put,
            Strike = 300m,
            Expiration = DateOnly.FromDateTime(asOf.UtcDateTime.Date.AddDays(-1)),
            OpenedAtUtc = asOf.AddDays(-7)
        });

        var provider = new FakeBrokerPositionsProvider(new BrokerPositionsSnapshot
        {
            AsOfUtc = asOf,
            Tickers = [new BrokerTickerSnapshot { Ticker = "MSFT", SharesOwned = 0 }]
        });

        var service = new WheelReconciliationService(repository, provider);

        var first = await service.ReconcileAsync();
        var second = await service.ReconcileAsync();

        Assert.Equal(1, first.UpdatedTickers);
        Assert.Equal(0, second.UpdatedTickers);
        Assert.Equal(1, repository.Events.Count(e => e.EventType == WheelEventType.Expired));
    }

    private sealed class FakeBrokerPositionsProvider(BrokerPositionsSnapshot snapshot) : IBrokerPositionsProvider
    {
        public Task<BrokerPositionsSnapshot> GetSnapshotAsync(
            IReadOnlyCollection<string>? tickers = null,
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult(snapshot);
        }
    }

    private sealed class InMemoryWheelStateRepository : IWheelStateRepository
    {
        private readonly Dictionary<string, WheelTickerState> _states = new();
        public List<WheelEvent> Events { get; } = [];

        public Task<WheelTickerState?> GetByTickerAsync(Ticker ticker, CancellationToken cancellationToken = default)
        {
            _states.TryGetValue((string)ticker, out var state);
            return Task.FromResult(state);
        }

        public Task<IReadOnlyList<Ticker>> ListTickersAsync(CancellationToken cancellationToken = default)
            => Task.FromResult((IReadOnlyList<Ticker>)_states.Keys.Select(k => new Ticker(k)).ToList());

        public Task<WheelTickerState> UpsertAsync(WheelTickerState state, CancellationToken cancellationToken = default)
        {
            var key = (string)state.Ticker;
            if (_states.TryGetValue(key, out var existing))
                state.Version = existing.Version + 1;
            else
                state.Version = 1;

            _states[key] = state;

            return Task.FromResult(state);
        }

        public Task AppendEventAsync(WheelEvent wheelEvent, CancellationToken cancellationToken = default)
        {
            Events.Add(wheelEvent);
            return Task.CompletedTask;
        }

        public Task<IReadOnlyList<WheelEvent>> GetEventsAsync(Ticker ticker, CancellationToken cancellationToken = default)
            => Task.FromResult((IReadOnlyList<WheelEvent>)Events.Where(e => e.Ticker == ticker).ToList());

        public Task<bool> HasReconciledBucketAsync(Ticker ticker, string bucket, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(Events.Any(e =>
                e.Ticker == ticker &&
                e.EventType == WheelEventType.Reconciled &&
                e.MetadataJson is not null &&
                e.MetadataJson.RootElement.TryGetProperty("bucket", out var property) &&
                string.Equals(property.GetString(), bucket, StringComparison.Ordinal)));
        }
    }
}
