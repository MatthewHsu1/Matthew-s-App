using FinancialApp.Domain.Options.AlphaVantage;
using FinancialApp.Domain.Options.Redis;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace FinancialApp.Infrastructure.DependencyInjection
{
    internal static class OptionsDI
    {
        public static IServiceCollection AddOptions(this IServiceCollection services, IConfiguration configuration)
        {
            services.Configure<AlphaVantageOptions>(configuration.GetSection(AlphaVantageOptions.SectionName));

            services.Configure<RedisOptions>(configuration.GetSection(RedisOptions.SectionName));

            return services;
        }
    }
}
