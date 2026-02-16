using Backend.Domain.Options.AlphaVantage;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Polly;
using Polly.RateLimiting;
using Polly.Retry;
using System.Threading.RateLimiting;

namespace Backend.Infrastructure.DependencyInjection
{
    internal static class RateLimitingDI
    {
        public static IServiceCollection AddRateLimiting(this IServiceCollection services)
        {
            const string AlphaVantageClientName = "AlphaVantage";

            services.AddHttpClient(AlphaVantageClientName)
                .ConfigureHttpClient((sp, client) =>
                {
                    var options = sp.GetRequiredService<IOptions<AlphaVantageOptions>>().Value;
                    client.BaseAddress = new Uri(options.BaseUrl.TrimEnd('/') + "/");
                })
                .AddResilienceHandler("alpha-vantage-rate-limit", builder =>
                {
                    builder.AddRateLimiter(new FixedWindowRateLimiter(new FixedWindowRateLimiterOptions
                    {
                        PermitLimit = 5,
                        Window = TimeSpan.FromMinutes(1),
                        QueueLimit = 0
                    }));

                    builder.AddRetry(new RetryStrategyOptions<HttpResponseMessage>
                    {
                        MaxRetryAttempts = 3,
                        BackoffType = DelayBackoffType.Exponential,
                        UseJitter = true,
                        Delay = TimeSpan.FromSeconds(2),
                        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
                            .HandleResult(r => (int)r.StatusCode >= 500)
                            .HandleResult(r => r.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
                            .Handle<HttpRequestException>()
                            .Handle<TaskCanceledException>()
                            .Handle<RateLimiterRejectedException>(),
                        OnRetry = args =>
                        {
                            return ValueTask.CompletedTask;
                        }
                    });
                });

            return services;
        }
    }
}
