# Ticker Value Object — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace four duplicate `NormalizeTicker`/`TickerHelper.Normalize` implementations with a single `Ticker` value object in `Backend.Domain` that enforces normalization at construction time.

**Architecture:** A `readonly record struct Ticker` lives in `Backend.Domain/Models/Wheel/`. Domain models (`WheelTickerState`, `WheelEvent`) use it as the type for their `Ticker` property. All application interfaces and services accept/return `Ticker` for ticker-typed parameters. EF entities stay as `string`; the repository mappers handle the boundary. The Api layer constructs `new Ticker(routeParam)` at the HTTP entry points.

**Tech Stack:** .NET 10, C#, xUnit (tests), EF Core + PostgreSQL (infrastructure, untouched by this change)

**Solution file:** `backend-dotnet/Backend.sln`
**Build command:** `dotnet build backend-dotnet/Backend.sln`
**Test command:** `dotnet test backend-dotnet/Backend.sln`

**Design doc:** `docs/plans/2026-02-19-ticker-value-object-design.md`

---

## Task 1: `Ticker` value object + unit tests

**Files:**
- Create: `backend-dotnet/src/Backend.Domain/Models/Wheel/Ticker.cs`
- Create: `backend-dotnet/tests/Backend.Infrastructure.Tests/Wheel/TickerTests.cs`

### Step 1: Write the failing tests

Create `backend-dotnet/tests/Backend.Infrastructure.Tests/Wheel/TickerTests.cs`:

```csharp
using Backend.Domain.Models.Wheel;

namespace Backend.Infrastructure.Tests.Wheel;

public class TickerTests
{
    [Theory]
    [InlineData("aapl", "AAPL")]
    [InlineData("  msft  ", "MSFT")]
    [InlineData("TSLA", "TSLA")]
    [InlineData(" nvda", "NVDA")]
    public void Constructor_NormalizesValue(string input, string expected)
    {
        var ticker = new Ticker(input);
        Assert.Equal(expected, ticker.Value);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void Constructor_Throws_WhenValueIsEmptyOrWhitespace(string input)
    {
        Assert.Throws<ArgumentException>(() => new Ticker(input));
    }

    [Fact]
    public void ImplicitStringConversion_ReturnsValue()
    {
        var ticker = new Ticker("aapl");
        string s = ticker;
        Assert.Equal("AAPL", s);
    }

    [Fact]
    public void ToString_ReturnsValue()
    {
        var ticker = new Ticker("msft");
        Assert.Equal("MSFT", ticker.ToString());
    }

    [Fact]
    public void StructuralEquality_TwoTickersWithSameSymbol_AreEqual()
    {
        var a = new Ticker("aapl");
        var b = new Ticker("AAPL");
        Assert.Equal(a, b);
    }
}
```

### Step 2: Run to verify it fails

```
dotnet test backend-dotnet/Backend.sln --filter "FullyQualifiedName~TickerTests"
```

Expected: fails with type-not-found errors (Ticker doesn't exist yet).

### Step 3: Create the `Ticker` value object

Create `backend-dotnet/src/Backend.Domain/Models/Wheel/Ticker.cs`:

```csharp
namespace Backend.Domain.Models.Wheel
{
    /// <summary>
    /// A normalized ticker symbol (e.g. stock underlying). Always uppercase and trimmed.
    /// </summary>
    public readonly record struct Ticker
    {
        /// <summary>
        /// The normalized ticker string value.
        /// </summary>
        public string Value { get; }

        /// <summary>
        /// Initializes a <see cref="Ticker"/> by trimming and uppercasing <paramref name="value"/>.
        /// </summary>
        /// <param name="value">Raw ticker symbol. Must not be empty or whitespace.</param>
        /// <exception cref="ArgumentException">Thrown when <paramref name="value"/> is empty or whitespace.</exception>
        public Ticker(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                throw new ArgumentException("Ticker cannot be empty or whitespace.", nameof(value));
            Value = value.Trim().ToUpperInvariant();
        }

        /// <summary>
        /// Implicitly converts a <see cref="Ticker"/> to its string value.
        /// </summary>
        public static implicit operator string(Ticker t) => t.Value;

        /// <inheritdoc />
        public override string ToString() => Value;
    }
}
```

### Step 4: Run tests and verify they pass

```
dotnet test backend-dotnet/Backend.sln --filter "FullyQualifiedName~TickerTests"
```

Expected: all 8 tests pass.

### Step 5: Commit

```
git add backend-dotnet/src/Backend.Domain/Models/Wheel/Ticker.cs
git add backend-dotnet/tests/Backend.Infrastructure.Tests/Wheel/TickerTests.cs
git commit -m "feat: add Ticker value object to Backend.Domain"
```

---

## Task 2: Update domain models to use `Ticker`

**Files:**
- Modify: `backend-dotnet/src/Backend.Domain/Models/Wheel/WheelTickerState.cs`
- Modify: `backend-dotnet/src/Backend.Domain/Models/Wheel/WheelEvent.cs`

> **Note:** After this task the solution will not compile until Tasks 3–7 are complete. That is expected. Complete all tasks before running a build.

### Step 1: Update `WheelTickerState`

Change `public string Ticker { get; set; } = string.Empty;` to:

```csharp
/// <summary>
/// Underlying ticker symbol (normalized).
/// </summary>
public Ticker Ticker { get; set; }
```

Remove the `= string.Empty` default — `Ticker` is a struct and has its own default.

### Step 2: Update `WheelEvent`

Change `public string Ticker { get; set; } = string.Empty;` to:

```csharp
/// <summary>
/// Underlying ticker symbol.
/// </summary>
public Ticker Ticker { get; set; }
```

### Step 3: No commit yet — continue to Task 3

---

## Task 3: Update application interfaces

**Files:**
- Modify: `backend-dotnet/src/Backend.Application/Interfaces/IWheelStateRepository.cs`
- Modify: `backend-dotnet/src/Backend.Application/Interfaces/IWheelStateService.cs`
- Modify: `backend-dotnet/src/Backend.Application/Interfaces/IWheelReconciliationService.cs`

### Step 1: Update `IWheelStateRepository`

Replace the entire file:

```csharp
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
```

### Step 2: Update `IWheelStateService`

Change `GetByTickerAsync(string ticker, ...)` to `GetByTickerAsync(Ticker ticker, ...)`:

```csharp
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
```

### Step 3: Update `IWheelReconciliationService`

Change `IReadOnlyCollection<string>?` to `IReadOnlyCollection<Ticker>?`:

```csharp
using Backend.Domain.Models.Wheel;
using Backend.Application.Models.Wheel;

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
```

### Step 4: No commit yet — continue to Task 4

---

## Task 4: Update `WheelStateService`

**Files:**
- Modify: `backend-dotnet/src/Backend.Application/Services/WheelStateService.cs`

### Step 1: Rewrite the service

Replace the entire file:

```csharp
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
```

> Note: The `string.IsNullOrWhiteSpace(state.Ticker)` check is removed — `Ticker` construction already throws for empty/whitespace. The `state.Ticker = normalizedTicker` line is removed because `state.Ticker` is now a `Ticker` value object that is already normalized.

### Step 2: No commit yet — continue to Task 5

---

## Task 5: Update `WheelReconciliationService`

**Files:**
- Modify: `backend-dotnet/src/Backend.Application/Services/WheelReconciliationService.cs`

### Step 1: Rewrite the service

Replace the entire file:

```csharp
using Backend.Application.Interfaces;
using Backend.Application.Models.Wheel;
using Backend.Domain.Models.Wheel;
using System.Text.Json;

namespace Backend.Application.Services
{
    /// <inheritdoc />
    public sealed class WheelReconciliationService(
        IWheelStateRepository repository,
        IBrokerPositionsProvider brokerPositionsProvider) : IWheelReconciliationService
    {
        /// <inheritdoc />
        public async Task<WheelReconciliationResult> ReconcileAsync(
            IReadOnlyCollection<Ticker>? tickers = null,
            CancellationToken cancellationToken = default)
        {
            var targetTickers = tickers is { Count: > 0 }
                ? tickers.Distinct().ToArray()
                : (await repository.ListTickersAsync(cancellationToken)).ToArray();

            if (targetTickers.Length == 0)
                return new WheelReconciliationResult();

            var snapshot = await brokerPositionsProvider.GetSnapshotAsync(
                targetTickers.Select(t => t.Value).ToArray(),
                cancellationToken);

            var snapshotByTicker = snapshot.Tickers
                .GroupBy(t => new Ticker(t.Ticker))
                .ToDictionary(g => g.Key, g => g.Last());

            var result = new WheelReconciliationResult { ProcessedTickers = targetTickers.Length };
            var bucket = snapshot.AsOfUtc.UtcDateTime.ToString("yyyyMMddHH");

            foreach (var ticker in targetTickers)
            {
                if (await repository.HasReconciledBucketAsync(ticker, bucket, cancellationToken))
                    continue;

                var state = await repository.GetByTickerAsync(ticker, cancellationToken);
                if (state is null)
                    continue;

                snapshotByTicker.TryGetValue(ticker, out var brokerTicker);

                var touched = false;
                var eventType = WheelEventType.Reconciled;
                var closeReason = (OptionCloseReason?)null;
                var before = CopyState(state);

                if (state.ActiveOption != ActiveOptionType.None)
                {
                    var optionMatch = IsOptionMatch(state, brokerTicker?.OpenOption);

                    if (!optionMatch)
                    {
                        var assigned = brokerTicker is not null && brokerTicker.SharesOwned != state.SharesOwned;

                        if (assigned)
                        {
                            CloseOption(state);
                            ApplyShares(state, brokerTicker!);
                            touched = true;
                            eventType = WheelEventType.Assigned;
                            closeReason = OptionCloseReason.Assigned;
                        }
                        else if (state.Expiration.HasValue && state.Expiration.Value < DateOnly.FromDateTime(snapshot.AsOfUtc.UtcDateTime.Date))
                        {
                            CloseOption(state);
                            touched = true;
                            eventType = WheelEventType.Expired;
                            closeReason = OptionCloseReason.Expired;
                        }
                    }
                }

                if (!touched && brokerTicker is not null && (brokerTicker.SharesOwned != state.SharesOwned || brokerTicker.CostBasis != state.CostBasis))
                {
                    ApplyShares(state, brokerTicker);
                    touched = true;
                    eventType = WheelEventType.SharesUpdated;
                }

                if (!touched)
                    continue;

                var updated = await repository.UpsertAsync(state, cancellationToken);

                await repository.AppendEventAsync(new WheelEvent
                {
                    Ticker = ticker,
                    EventType = eventType,
                    OccurredAtUtc = snapshot.AsOfUtc,
                    ActiveOptionBefore = before.ActiveOption,
                    ActiveOptionAfter = updated.ActiveOption,
                    SharesOwnedBefore = before.SharesOwned,
                    SharesOwnedAfter = updated.SharesOwned,
                    CostBasisBefore = before.CostBasis,
                    CostBasisAfter = updated.CostBasis,
                    CloseReason = closeReason,
                    MetadataJson = CreateBucketMetadata(bucket)
                }, cancellationToken);

                await repository.AppendEventAsync(new WheelEvent
                {
                    Ticker = ticker,
                    EventType = WheelEventType.Reconciled,
                    OccurredAtUtc = snapshot.AsOfUtc,
                    ActiveOptionBefore = before.ActiveOption,
                    ActiveOptionAfter = updated.ActiveOption,
                    SharesOwnedBefore = before.SharesOwned,
                    SharesOwnedAfter = updated.SharesOwned,
                    CostBasisBefore = before.CostBasis,
                    CostBasisAfter = updated.CostBasis,
                    MetadataJson = CreateBucketMetadata(bucket)
                }, cancellationToken);

                result.UpdatedTickers++;
                result.EventsAppended += 2;
            }

            return result;
        }

        private static WheelTickerState CopyState(WheelTickerState state) => new()
        {
            Ticker = state.Ticker,
            HasShares = state.HasShares,
            SharesOwned = state.SharesOwned,
            CostBasis = state.CostBasis,
            ActiveOption = state.ActiveOption,
            Strike = state.Strike,
            Expiration = state.Expiration,
            OpenPremium = state.OpenPremium,
            OpenedAtUtc = state.OpenedAtUtc,
            UpdatedAtUtc = state.UpdatedAtUtc,
            Version = state.Version
        };

        private static void ApplyShares(WheelTickerState state, BrokerTickerSnapshot brokerTicker)
        {
            state.SharesOwned = brokerTicker.SharesOwned;
            state.HasShares = brokerTicker.SharesOwned > 0;
            state.CostBasis = brokerTicker.SharesOwned > 0 ? brokerTicker.CostBasis : null;
        }

        private static void CloseOption(WheelTickerState state)
        {
            state.ActiveOption = ActiveOptionType.None;
            state.Strike = null;
            state.Expiration = null;
            state.OpenPremium = null;
            state.OpenedAtUtc = null;
        }

        private static bool IsOptionMatch(WheelTickerState state, BrokerOptionSnapshot? option)
        {
            if (option is null)
                return false;

            return option.Type == state.ActiveOption
                && state.Strike.HasValue
                && state.Expiration.HasValue
                && option.Strike == state.Strike.Value
                && option.Expiration == state.Expiration.Value;
        }

        private static JsonDocument CreateBucketMetadata(string bucket)
        {
            using var document = JsonDocument.Parse($$"""{"bucket":"{{bucket}}"}""");
            return JsonDocument.Parse(document.RootElement.GetRawText());
        }
    }
}
```

> Changes: `NormalizeTicker` private method deleted. `tickers.Select(NormalizeTicker).Distinct(StringComparer.OrdinalIgnoreCase)` replaced with `tickers.Distinct()` (structural equality on `Ticker` handles this). Broker call passes `.Select(t => t.Value).ToArray()`. `snapshotByTicker` keyed by `new Ticker(t.Ticker)` to normalize broker-side strings. `WheelEvent.Ticker = ticker` now works directly since `ticker` is already `Ticker`.

### Step 2: No commit yet — continue to Task 6

---

## Task 6: Update `WheelStateRepository`

**Files:**
- Modify: `backend-dotnet/src/Backend.Infrastructure/Repositories/WheelStateRepository.cs`

### Step 1: Rewrite the repository

Replace the entire file:

```csharp
using Backend.Application.Interfaces;
using Backend.Domain.Models.Wheel;
using Backend.Infrastructure.Data;
using Backend.Infrastructure.Data.Entities;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using System.Text.Json;

namespace Backend.Infrastructure.Repositories
{
    /// <inheritdoc />
    public sealed class WheelStateRepository(AppDbContext dbContext)
        : IWheelStateRepository
    {
        /// <inheritdoc />
        public async Task<WheelTickerState?> GetByTickerAsync(Ticker ticker, CancellationToken cancellationToken = default)
        {
            var entity = await dbContext.WheelTickerStates
                .AsNoTracking()
                .SingleOrDefaultAsync(x => x.Ticker == (string)ticker, cancellationToken);

            return entity is null ? null : MapState(entity);
        }

        /// <inheritdoc />
        public async Task<IReadOnlyList<Ticker>> ListTickersAsync(CancellationToken cancellationToken = default)
        {
            var strings = await dbContext.WheelTickerStates
                .AsNoTracking()
                .OrderBy(x => x.Ticker)
                .Select(x => x.Ticker)
                .ToListAsync(cancellationToken);

            return strings.Select(s => new Ticker(s)).ToList();
        }

        /// <inheritdoc />
        public async Task<WheelTickerState> UpsertAsync(WheelTickerState state, CancellationToken cancellationToken = default)
        {
            var entity = await dbContext.WheelTickerStates
                .SingleOrDefaultAsync(x => x.Ticker == (string)state.Ticker, cancellationToken);

            if (entity is null)
            {
                entity = new WheelTickerStateEntity
                {
                    Ticker = state.Ticker,
                    Version = 1
                };

                ApplyState(entity, state);
                entity.UpdatedAtUtc = DateTimeOffset.UtcNow;

                dbContext.WheelTickerStates.Add(entity);
                await dbContext.SaveChangesAsync(cancellationToken);

                return MapState(entity);
            }

            if (state.Version != entity.Version)
                throw new DbUpdateConcurrencyException($"Version mismatch for {state.Ticker}. Expected {entity.Version}, got {state.Version}.");

            ApplyState(entity, state);
            entity.UpdatedAtUtc = DateTimeOffset.UtcNow;
            entity.Version += 1;

            await dbContext.SaveChangesAsync(cancellationToken);
            return MapState(entity);
        }

        /// <inheritdoc />
        public async Task AppendEventAsync(WheelEvent wheelEvent, CancellationToken cancellationToken = default)
        {
            var entity = new WheelEventEntity
            {
                Ticker = wheelEvent.Ticker,
                EventType = wheelEvent.EventType,
                OccurredAtUtc = wheelEvent.OccurredAtUtc,
                ActiveOptionBefore = wheelEvent.ActiveOptionBefore,
                ActiveOptionAfter = wheelEvent.ActiveOptionAfter,
                SharesOwnedBefore = wheelEvent.SharesOwnedBefore,
                SharesOwnedAfter = wheelEvent.SharesOwnedAfter,
                CostBasisBefore = wheelEvent.CostBasisBefore,
                CostBasisAfter = wheelEvent.CostBasisAfter,
                CloseReason = wheelEvent.CloseReason,
                MetadataJson = wheelEvent.MetadataJson
            };

            dbContext.WheelEvents.Add(entity);
            await dbContext.SaveChangesAsync(cancellationToken);
        }

        /// <inheritdoc />
        public async Task<IReadOnlyList<WheelEvent>> GetEventsAsync(Ticker ticker, CancellationToken cancellationToken = default)
        {
            var entities = await dbContext.WheelEvents
                .AsNoTracking()
                .Where(x => x.Ticker == (string)ticker)
                .OrderBy(x => x.OccurredAtUtc)
                .ThenBy(x => x.Id)
                .ToListAsync(cancellationToken);

            return entities.Select(MapEvent).ToList();
        }

        /// <inheritdoc />
        public async Task<bool> HasReconciledBucketAsync(Ticker ticker, string bucket, CancellationToken cancellationToken = default)
        {
            var bucketMetadata = JsonSerializer.Serialize(new { bucket });
            var sql = """
                SELECT EXISTS (
                    SELECT 1
                    FROM wheel_events
                    WHERE "Ticker" = @ticker
                      AND "EventType" = @eventType
                      AND "MetadataJson" IS NOT NULL
                      AND "MetadataJson" @> CAST(@metadata AS jsonb)
                ) AS "Value"
                """;

            var exists = await dbContext.Database.SqlQueryRaw<bool>(
                sql,
                new NpgsqlParameter("ticker", (string)ticker),
                new NpgsqlParameter("eventType", (short)WheelEventType.Reconciled),
                new NpgsqlParameter("metadata", bucketMetadata))
                .SingleAsync(cancellationToken);

            return exists;
        }

        private static WheelTickerState MapState(WheelTickerStateEntity entity) => new()
        {
            Ticker = new Ticker(entity.Ticker),
            HasShares = entity.HasShares,
            SharesOwned = entity.SharesOwned,
            CostBasis = entity.CostBasis,
            ActiveOption = entity.ActiveOption,
            Strike = entity.Strike,
            Expiration = entity.Expiration,
            OpenPremium = entity.OpenPremium,
            OpenedAtUtc = entity.OpenedAtUtc,
            UpdatedAtUtc = entity.UpdatedAtUtc,
            Version = entity.Version
        };

        private static WheelEvent MapEvent(WheelEventEntity entity) => new()
        {
            Id = entity.Id,
            Ticker = new Ticker(entity.Ticker),
            EventType = entity.EventType,
            OccurredAtUtc = entity.OccurredAtUtc,
            ActiveOptionBefore = entity.ActiveOptionBefore,
            ActiveOptionAfter = entity.ActiveOptionAfter,
            SharesOwnedBefore = entity.SharesOwnedBefore,
            SharesOwnedAfter = entity.SharesOwnedAfter,
            CostBasisBefore = entity.CostBasisBefore,
            CostBasisAfter = entity.CostBasisAfter,
            CloseReason = entity.CloseReason,
            MetadataJson = entity.MetadataJson
        };

        private static void ApplyState(WheelTickerStateEntity entity, WheelTickerState state)
        {
            entity.Ticker = state.Ticker;
            entity.HasShares = state.HasShares;
            entity.SharesOwned = state.SharesOwned;
            entity.CostBasis = state.CostBasis;
            entity.ActiveOption = state.ActiveOption;
            entity.Strike = state.Strike;
            entity.Expiration = state.Expiration;
            entity.OpenPremium = state.OpenPremium;
            entity.OpenedAtUtc = state.OpenedAtUtc;
        }
    }
}
```

> Key changes: `NormalizeTicker` deleted. EF LINQ expressions use `(string)ticker` explicit cast to avoid any expression translator ambiguity. `entity.Ticker = state.Ticker` and `entity.Ticker = wheelEvent.Ticker` compile via `implicit operator string`. `MapState` and `MapEvent` construct `new Ticker(entity.Ticker)` from the already-normalized DB string.

### Step 2: No commit yet — continue to Task 7

---

## Task 7: Update `WheelStateController` and delete `TickerHelper`

**Files:**
- Modify: `backend-dotnet/src/Backend.Api/Controllers/WheelStateController.cs`
- Delete: `backend-dotnet/src/Backend.Api/Helpers/TickerHelper.cs`

### Step 1: Rewrite `WheelStateController`

Replace the entire file:

```csharp
using Backend.Api.Contracts.Wheel;
using Backend.Application.Interfaces;
using Backend.Domain.Models.Wheel;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Backend.Api.Controllers;

[ApiController]
[Route("api/wheel-state")]
public sealed class WheelStateController(
    IWheelStateService wheelStateService,
    IWheelReconciliationService reconciliationService) : ControllerBase
{
    [HttpGet("{ticker}")]
    [ProducesResponseType(typeof(WheelStateResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetByTickerAsync(string ticker, CancellationToken cancellationToken)
    {
        var normalizedTicker = new Ticker(ticker);
        var state = await wheelStateService.GetByTickerAsync(normalizedTicker, cancellationToken);

        if (state is null)
            return NotFound();

        return Ok(ToResponse(state));
    }

    [HttpPut("{ticker}")]
    [ProducesResponseType(typeof(WheelStateResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(WheelStateResponse), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> UpsertAsync(
        string ticker,
        [FromBody] UpsertWheelStateRequest request,
        CancellationToken cancellationToken)
    {
        var normalizedTicker = new Ticker(ticker);
        var existing = await wheelStateService.GetByTickerAsync(normalizedTicker, cancellationToken);

        var model = new WheelTickerState
        {
            Ticker = normalizedTicker,
            HasShares = request.HasShares,
            SharesOwned = request.SharesOwned,
            CostBasis = request.CostBasis,
            ActiveOption = request.ActiveOption,
            Strike = request.Strike,
            Expiration = request.Expiration,
            OpenPremium = request.OpenPremium,
            OpenedAtUtc = request.OpenedAtUtc,
            Version = request.Version ?? existing?.Version ?? 0
        };

        try
        {
            var updated = await wheelStateService.UpsertAsync(model, cancellationToken);
            var response = ToResponse(updated);

            if (existing is null)
                return CreatedAtAction(nameof(GetByTickerAsync), new { ticker = normalizedTicker.Value }, response);

            return Ok(response);
        }
        catch (ArgumentException ex)
        {
            return ValidationProblem(ex.Message);
        }
        catch (DbUpdateConcurrencyException ex)
        {
            return Conflict(new { message = ex.Message });
        }
    }

    [HttpPost("reconcile")]
    [ProducesResponseType(typeof(WheelReconcileResponse), StatusCodes.Status202Accepted)]
    public async Task<IActionResult> ReconcileAsync(
        [FromBody] ReconcileWheelStateRequest? request,
        CancellationToken cancellationToken)
    {
        IReadOnlyCollection<Ticker>? tickers = null;
        if (request?.Tickers is { Count: > 0 } rawTickers)
            tickers = rawTickers.Select(t => new Ticker(t)).Distinct().ToArray();

        var result = await reconciliationService.ReconcileAsync(tickers, cancellationToken);

        return Accepted(new WheelReconcileResponse
        {
            ProcessedTickers = result.ProcessedTickers,
            UpdatedTickers = result.UpdatedTickers,
            EventsAppended = result.EventsAppended
        });
    }

    private static WheelStateResponse ToResponse(WheelTickerState state)
    {
        return new WheelStateResponse
        {
            Ticker = state.Ticker.Value,
            HasShares = state.HasShares,
            SharesOwned = state.SharesOwned,
            CostBasis = state.CostBasis,
            ActiveOption = state.ActiveOption,
            Strike = state.Strike,
            Expiration = state.Expiration,
            OpenPremium = state.OpenPremium,
            OpenedAtUtc = state.OpenedAtUtc,
            UpdatedAtUtc = state.UpdatedAtUtc,
            Version = state.Version
        };
    }
}
```

> Key changes: `using Backend.Api.Helpers` removed. All `TickerHelper.Normalize(ticker)` replaced with `new Ticker(ticker)`. `new Ticker(ticker)` can throw `ArgumentException` on blank input — the controller's existing `ArgumentException` catch in `UpsertAsync` handles validation errors already; for `GetByTickerAsync` a blank ticker route segment is effectively unreachable via valid HTTP routing. `ToResponse` uses `state.Ticker.Value` to get the string. `ReconcileAsync` uses `Distinct()` which works via structural equality on `Ticker`.

### Step 2: Delete `TickerHelper.cs`

Delete the file `backend-dotnet/src/Backend.Api/Helpers/TickerHelper.cs`.

### Step 3: Build the entire solution — verify it compiles

```
dotnet build backend-dotnet/Backend.sln
```

Expected: **Build succeeded** with 0 errors.

### Step 4: Commit

```
git add -A
git commit -m "feat: replace NormalizeTicker copies with Ticker value object"
```

---

## Task 8: Update tests

**Files:**
- Modify: `backend-dotnet/tests/Backend.Infrastructure.Tests/Wheel/WheelStateRepositoryIntegrationTests.cs`
- Modify: `backend-dotnet/tests/Backend.Infrastructure.Tests/Wheel/WheelStateServiceTests.cs`
- Modify: `backend-dotnet/tests/Backend.Infrastructure.Tests/Wheel/WheelReconciliationServiceTests.cs`

### Step 1: Update `WheelStateRepositoryIntegrationTests`

All `Ticker = "..."` string literals become `Ticker = new Ticker("...")`.  
All `Assert.Equal("AAPL", created.Ticker)` become `Assert.Equal("AAPL", created.Ticker.Value)`.  
`GetEventsAsync("MSFT")` and `HasReconciledBucketAsync("MSFT", ...)` calls change to `new Ticker("MSFT")`.

Full updated file:

```csharp
using Backend.Domain.Models.Wheel;
using Backend.Infrastructure.Data;
using Backend.Infrastructure.Repositories;
using System.Text.Json;

namespace Backend.Infrastructure.Tests.Wheel;

public class WheelStateRepositoryIntegrationTests
{
    [Fact]
    public async Task UpsertAsync_InsertsAndUpdatesState_WithVersionIncrement()
    {
        var (options, schema) = await PostgresTestDb.CreateOptionsAsync();
        if (options is null)
            return;

        try
        {
            await using var db = new AppDbContext(options);
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
        finally
        {
            await PostgresTestDb.CleanupSchemaAsync(options, schema);
        }
    }

    [Fact]
    public async Task AppendEventAsync_PersistsOrderedEvents()
    {
        var (options, schema) = await PostgresTestDb.CreateOptionsAsync();
        if (options is null)
            return;

        try
        {
            await using var db = new AppDbContext(options);
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
        finally
        {
            await PostgresTestDb.CleanupSchemaAsync(options, schema);
        }
    }

    [Fact]
    public async Task HasReconciledBucketAsync_ReturnsTrue_ForMatchingBucketMetadata()
    {
        var (options, schema) = await PostgresTestDb.CreateOptionsAsync();
        if (options is null)
            return;

        try
        {
            await using var db = new AppDbContext(options);
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
        finally
        {
            await PostgresTestDb.CleanupSchemaAsync(options, schema);
        }
    }
}
```

### Step 2: Update `WheelStateServiceTests`

Update the inline `InMemoryWheelStateRepository` to match the new interface signatures. Update object initializers and assertions.

Full updated file:

```csharp
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
```

### Step 3: Update `WheelReconciliationServiceTests`

Update the inline `InMemoryWheelStateRepository` to match new interface signatures. Update all `Ticker = "..."` to `Ticker = new Ticker("...")`. Update calls to repository methods like `GetByTickerAsync("AAPL")` to `GetByTickerAsync(new Ticker("AAPL"))`.

Full updated file:

```csharp
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
        await repository.UpsertAsync(new WheelTickerState
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
        private readonly Dictionary<Ticker, WheelTickerState> _states = [];
        public List<WheelEvent> Events { get; } = [];

        public Task<WheelTickerState?> GetByTickerAsync(Ticker ticker, CancellationToken cancellationToken = default)
        {
            _states.TryGetValue(ticker, out var state);
            return Task.FromResult(state);
        }

        public Task<IReadOnlyList<Ticker>> ListTickersAsync(CancellationToken cancellationToken = default)
            => Task.FromResult((IReadOnlyList<Ticker>)_states.Keys.ToList());

        public Task<WheelTickerState> UpsertAsync(WheelTickerState state, CancellationToken cancellationToken = default)
        {
            if (_states.TryGetValue(state.Ticker, out var existing))
                state.Version = existing.Version + 1;
            else
                state.Version = 1;

            _states[state.Ticker] = state;
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
```

> The in-memory dictionary is now keyed by `Ticker` (structural equality, no more `StringComparer.OrdinalIgnoreCase` needed). `e.Ticker == ticker` comparisons use `Ticker` structural equality. The `state.Ticker.ToUpperInvariant()` normalization is gone — `Ticker` construction handles it. `state.Ticker = key` string mutation is gone.

### Step 4: Run all tests

```
dotnet test backend-dotnet/Backend.sln
```

Expected: all tests pass (Postgres integration tests are skipped if no DB is available — that is normal).

### Step 5: Commit

```
git add -A
git commit -m "test: update tests to use Ticker value object"
```

---

## Task 9: Final verification

### Step 1: Clean build

```
dotnet build backend-dotnet/Backend.sln --no-incremental
```

Expected: Build succeeded, 0 errors, 0 warnings related to this change.

### Step 2: Full test run

```
dotnet test backend-dotnet/Backend.sln --verbosity normal
```

Expected: all unit tests pass.

### Step 3: Confirm deleted files

Verify `backend-dotnet/src/Backend.Api/Helpers/TickerHelper.cs` no longer exists.

### Step 4: Confirm no remaining `NormalizeTicker` or `TickerHelper` references

```
# PowerShell
Select-String -Path "backend-dotnet" -Pattern "NormalizeTicker|TickerHelper" -Recurse
```

Expected: no matches.
