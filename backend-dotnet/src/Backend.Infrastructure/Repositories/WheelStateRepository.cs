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
