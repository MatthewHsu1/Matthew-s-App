# Ticker Value Object — Design

**Date:** 2026-02-19  
**Status:** Approved

## Problem

`NormalizeTicker` / `TickerHelper.Normalize` (both `ticker.Trim().ToUpperInvariant()`) exists as four independent private copies:

| Copy | Location |
|---|---|
| `WheelStateRepository.NormalizeTicker` | `Backend.Infrastructure` |
| `WheelStateService.NormalizeTicker` | `Backend.Application` |
| `WheelReconciliationService.NormalizeTicker` | `Backend.Application` |
| `TickerHelper.Normalize` | `Backend.Api` |

Any change to normalization rules (e.g. strip non-alphanumeric characters) must be applied in four places. There is no enforcement: un-normalized strings can be passed anywhere without a compile error.

## Decision

Introduce a `Ticker` value object in `Backend.Domain`. Normalization becomes a domain invariant encoded in the type, making it impossible to construct an invalid or un-normalized ticker. All four duplicate copies are deleted.

## Value Object

**File:** `Backend.Domain/Models/Wheel/Ticker.cs`

```csharp
public readonly record struct Ticker
{
    public string Value { get; }

    public Ticker(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
            throw new ArgumentException("Ticker cannot be empty or whitespace.", nameof(value));
        Value = value.Trim().ToUpperInvariant();
    }

    public static implicit operator string(Ticker t) => t.Value;
    public override string ToString() => Value;
}
```

Key decisions:
- `readonly record struct` — value semantics, stack-allocated, structural equality for free
- Constructor validates and normalizes — normalization is enforced at construction, not at call sites
- `implicit operator string` — EF entity assignment and broker API calls work without explicit casts
- No `implicit operator Ticker(string)` — callers write `new Ticker(rawString)` deliberately at layer boundaries; normalization is never silent

## Layer-by-Layer Changes

### Domain (`Backend.Domain`)

- `Ticker.cs` added (new)
- `WheelTickerState.Ticker`: `string` → `Ticker`
- `WheelEvent.Ticker`: `string` → `Ticker`

### Application interfaces (`Backend.Application`)

- `IWheelStateRepository`
  - `GetByTickerAsync(string)` → `GetByTickerAsync(Ticker)`
  - `GetEventsAsync(string)` → `GetEventsAsync(Ticker)`
  - `HasReconciledBucketAsync(string, string)` → `HasReconciledBucketAsync(Ticker, string)`
  - `ListTickersAsync()` return type: `IReadOnlyList<string>` → `IReadOnlyList<Ticker>`
- `IWheelStateService`
  - `GetByTickerAsync(string)` → `GetByTickerAsync(Ticker)`
- `IWheelReconciliationService`
  - `ReconcileAsync(IReadOnlyCollection<string>?)` → `ReconcileAsync(IReadOnlyCollection<Ticker>?)`

### Application services (`Backend.Application`)

- `WheelStateService`: delete `NormalizeTicker`; accept `Ticker` at entry points
- `WheelReconciliationService`: delete `NormalizeTicker`; accept `IReadOnlyCollection<Ticker>?`; pass tickers to `IBrokerPositionsProvider` as strings via `.Select(t => t.Value).ToArray()`

### Infrastructure (`Backend.Infrastructure`)

- `WheelStateRepository`: delete `NormalizeTicker`
- `MapState` / `MapEvent`: `Ticker = new Ticker(entity.Ticker)`
- `ApplyState`: `entity.Ticker = state.Ticker` (compiles via `implicit operator string`)
- EF LINQ queries: use `(string)ticker` explicit cast for expression translator safety
- `ListTickersAsync`: `.Select(x => new Ticker(x.Ticker))` in projection

### Api (`Backend.Api`)

- `WheelStateController`: `TickerHelper.Normalize(ticker)` → `new Ticker(ticker)` at each route entry point
- `TickerHelper.cs`: deleted

### EF entities and migrations

- `WheelTickerStateEntity.Ticker` and `WheelEventEntity.Ticker` stay as `string`
- `AppDbContext` is unchanged
- No migration required — column type and data are unaffected

### External boundary

- `IBrokerPositionsProvider.GetSnapshotAsync(IReadOnlyCollection<string>?)` stays as `string` — it is an external integration boundary; the broker has no concept of `Ticker`

## Tests

- `WheelStateRepositoryIntegrationTests`: object initializers update `Ticker = "AAPL"` → `Ticker = new Ticker("AAPL")`; `Assert.Equal("AAPL", created.Ticker)` → `Assert.Equal("AAPL", created.Ticker.Value)`
- `WheelStateServiceTests`: `InMemoryWheelStateRepository` method signatures update to match new interface
- New unit tests for `Ticker` constructor: normalizes, trims, rejects empty/whitespace
