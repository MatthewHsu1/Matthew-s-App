using Backend.Application.Interfaces;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Backend.Application.Services
{
    /// <inheritdoc />
    public sealed class WheelReconciliationStartupService(
        IWheelReconciliationService reconciliationService,
        ILogger<WheelReconciliationStartupService> logger) : IHostedService
    {
        /// <inheritdoc />
        public async Task StartAsync(CancellationToken cancellationToken)
        {
            try
            {
                await reconciliationService.ReconcileAsync(cancellationToken: cancellationToken);
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Initial wheel reconciliation failed.");
            }
        }

        /// <inheritdoc />
        public Task StopAsync(CancellationToken cancellationToken)
            => Task.CompletedTask;
    }
}
