using Backend.Application.Options;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.Application.DependencyInjection
{
    internal static class OptionsDI
    {
        public static IServiceCollection AddOptions(this IServiceCollection services, IConfiguration configuration)
        {
            services.Configure<TechnicalIndicatorsCacheOptions>(configuration.GetSection(TechnicalIndicatorsCacheOptions.SectionName));

            return services;
        }
    }
}
