using FinancialApp.Application.Interfaces;
using FinancialApp.Application.Options;
using FinancialApp.Application.Services;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace FinancialApp.Application.DependencyInjection
{
    internal static class ServiceDI
    {
        public static IServiceCollection AddServices(this IServiceCollection service)
        {
            service.AddScoped<TechnicalIndicatorsService>();
            service.AddScoped<ITechnicalIndicatorsService>(sp =>
            {
                var inner = sp.GetRequiredService<TechnicalIndicatorsService>();
                var cache = sp.GetRequiredService<IDistributedCache>();
                var options = sp.GetRequiredService<IOptions<TechnicalIndicatorsCacheOptions>>();
                return new CachingTechnicalIndicatorsService(inner, cache, options);
            });

            return service;
        }
    }
}
