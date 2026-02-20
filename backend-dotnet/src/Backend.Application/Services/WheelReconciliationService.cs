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
            => JsonDocument.Parse($$"""{"bucket":"{{bucket}}"}""");
    }
}
