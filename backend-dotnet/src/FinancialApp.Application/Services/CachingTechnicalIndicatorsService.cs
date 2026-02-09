using FinancialApp.Application.Extensions;
using FinancialApp.Application.Interfaces;
using FinancialApp.Application.Options;
using FinancialApp.Domain.Models.MarketData;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.Extensions.Options;
using System.Text.Json;

namespace FinancialApp.Application.Services
{
    internal class CachingTechnicalIndicatorsService(ITechnicalIndicatorsService inner, IDistributedCache cache, IOptions<TechnicalIndicatorsCacheOptions> options)
        : ITechnicalIndicatorsService
    {
        private const string KeyPrefix = "indicators:";

        public async Task<TechnicalIndicatorsResult> GetIndicatorsAsync(string ticker, DateTime? asOfDate = null, CancellationToken cancellationToken = default)
        {
            var key = BuildKey(ticker, asOfDate);

            var bytes = await cache.GetAsync(key, cancellationToken).ConfigureAwait(false);

            if (bytes is { Length: > 0 })
            {
                var cached = JsonSerializer.Deserialize<TechnicalIndicatorsResult>(bytes, JSONExtensions.JsonCamelCaseOptions);

                if (cached is not null)
                    return cached;
            }

            var result = await inner.GetIndicatorsAsync(ticker, asOfDate, cancellationToken).ConfigureAwait(false);

            var durationMinutes = options.Value.CacheDurationMinutes;
            if (durationMinutes <= 0)
                durationMinutes = 10;

            var entryOptions = new DistributedCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(durationMinutes)
            };

            var serialized = JsonSerializer.SerializeToUtf8Bytes(result, JSONExtensions.JsonCamelCaseOptions);
            await cache.SetAsync(key, serialized, entryOptions, cancellationToken).ConfigureAwait(false);

            return result;
        }

        private static string BuildKey(string ticker, DateTime? asOfDate)
        {
            var datePart = asOfDate.HasValue ? asOfDate.Value.ToString("yyyy-MM-dd") : "latest";
            return $"{KeyPrefix}{ticker}:{datePart}";
        }
    }
}
