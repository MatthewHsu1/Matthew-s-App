using Backend.Application.Interfaces;
using Backend.Application.Models.Wheel;
using Microsoft.Extensions.Logging;

namespace Backend.Application.Services
{
    /// <inheritdoc />
    public sealed class NullBrokerPositionsProvider(ILogger<NullBrokerPositionsProvider> logger) : IBrokerPositionsProvider
    {
        /// <inheritdoc />
        public Task<BrokerPositionsSnapshot> GetSnapshotAsync(
            IReadOnlyCollection<string>? tickers = null,
            CancellationToken cancellationToken = default)
        {
            logger.LogWarning("Using null broker positions provider. Returning empty snapshot for reconciliation.");

            return Task.FromResult(new BrokerPositionsSnapshot
            {
                AsOfUtc = DateTimeOffset.UtcNow,
                Tickers = []
            });
        }
    }
}
