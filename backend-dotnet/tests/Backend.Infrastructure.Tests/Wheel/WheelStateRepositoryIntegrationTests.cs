using Backend.Domain.Models.Wheel;
using Backend.Infrastructure.Data;
using Backend.Infrastructure.Repositories;
using Backend.Testing.Database;
using System.Text.Json;

namespace Backend.Infrastructure.Tests.Wheel;

public class WheelStateRepositoryIntegrationTests
{
    [SkippableFact]
    public async Task UpsertAsync_InsertsAndUpdatesState_WithVersionIncrement()
    {
        await using var lease = await IntegrationTestDb.CreateAppDbContextLeaseAsync("wheel");
        Skip.If(lease is null, "Integration DB connection string not configured. Set BACKEND_TEST_DB_CONNECTION or app Supabase configuration.");

        await using var db = new AppDbContext(lease!.Options);
        var repository = new WheelStateRepository(db);

        var created = await repository.UpsertAsync(new WheelTickerState
        {
            Ticker = new Ticker("aapl"),
            HasShares = false,
            SharesOwned = 0,
            ActiveOption = ActiveOptionType.None
        });

        Assert.Equal("AAPL", created.Ticker.Value);
        Assert.Equal(1, created.Version);

        created.HasShares = true;
        created.SharesOwned = 100;
        created.CostBasis = 185.25m;

        var updated = await repository.UpsertAsync(created);

        Assert.Equal(2, updated.Version);
        Assert.True(updated.HasShares);
        Assert.Equal(100, updated.SharesOwned);
        Assert.Equal(185.25m, updated.CostBasis);
    }

    [SkippableFact]
    public async Task AppendEventAsync_PersistsOrderedEvents()
    {
        await using var lease = await IntegrationTestDb.CreateAppDbContextLeaseAsync("wheel");
        Skip.If(lease is null, "Integration DB connection string not configured. Set BACKEND_TEST_DB_CONNECTION or app Supabase configuration.");

        await using var db = new AppDbContext(lease!.Options);
        var repository = new WheelStateRepository(db);

        await repository.UpsertAsync(new WheelTickerState
        {
            Ticker = new Ticker("MSFT"),
            HasShares = true,
            SharesOwned = 100,
            CostBasis = 300m,
            ActiveOption = ActiveOptionType.None
        });

        await repository.AppendEventAsync(new WheelEvent
        {
            Ticker = new Ticker("MSFT"),
            EventType = WheelEventType.StateInitialized,
            OccurredAtUtc = DateTimeOffset.UtcNow,
            SharesOwnedBefore = 0,
            SharesOwnedAfter = 100
        });

        await repository.AppendEventAsync(new WheelEvent
        {
            Ticker = new Ticker("MSFT"),
            EventType = WheelEventType.Reconciled,
            OccurredAtUtc = DateTimeOffset.UtcNow.AddMinutes(1),
            SharesOwnedBefore = 100,
            SharesOwnedAfter = 100,
            MetadataJson = JsonDocument.Parse("{\"bucket\":\"2026021913\"}")
        });

        var events = await repository.GetEventsAsync(new Ticker("MSFT"));

        Assert.Equal(2, events.Count);
        Assert.Equal(WheelEventType.StateInitialized, events[0].EventType);
        Assert.Equal(WheelEventType.Reconciled, events[1].EventType);
    }

    [SkippableFact]
    public async Task HasReconciledBucketAsync_ReturnsTrue_ForMatchingBucketMetadata()
    {
        await using var lease = await IntegrationTestDb.CreateAppDbContextLeaseAsync("wheel");
        Skip.If(lease is null, "Integration DB connection string not configured. Set BACKEND_TEST_DB_CONNECTION or app Supabase configuration.");

        await using var db = new AppDbContext(lease!.Options);
        var repository = new WheelStateRepository(db);

        await repository.UpsertAsync(new WheelTickerState
        {
            Ticker = new Ticker("MSFT"),
            HasShares = true,
            SharesOwned = 100,
            CostBasis = 300m,
            ActiveOption = ActiveOptionType.None
        });

        await repository.AppendEventAsync(new WheelEvent
        {
            Ticker = new Ticker("MSFT"),
            EventType = WheelEventType.Reconciled,
            OccurredAtUtc = DateTimeOffset.UtcNow,
            MetadataJson = JsonDocument.Parse("{ \"bucket\" : \"2026021913\" }")
        });

        var hasBucket = await repository.HasReconciledBucketAsync(new Ticker("MSFT"), "2026021913");

        Assert.True(hasBucket);
    }
}
