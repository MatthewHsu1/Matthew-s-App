using FinancialApp.Domain.Models.AlphaVantage;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Polly;
using System.Threading.RateLimiting;

namespace FinancialApp.Infrastructure.DependencyInjection
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
                });

            return services;
        }
    }
}
