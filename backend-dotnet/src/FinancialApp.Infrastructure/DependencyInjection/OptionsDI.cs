using FinancialApp.Domain.Models.AlphaVantage;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace FinancialApp.Infrastructure.DependencyInjection
{
    internal static class OptionsDI
    {
        public static IServiceCollection AddOptions(this IServiceCollection services, IConfiguration configuration)
        {
            services.Configure<AlphaVantageOptions>(configuration.GetSection(AlphaVantageOptions.SectionName));

            return services;
        }
    }
}
