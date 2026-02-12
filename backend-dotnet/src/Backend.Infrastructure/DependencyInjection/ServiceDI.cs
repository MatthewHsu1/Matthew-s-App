using Backend.Domain.Interfaces;
using Backend.Infrastructure.Services.AlphaVantage;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.Infrastructure.DependencyInjection
{
    internal static class ServiceDI
    {
        public static IServiceCollection AddServices(this IServiceCollection service)
        {
            service.AddScoped<IMarketDataService, AlphaVantageMarketDataService>();

            return service;
        }
    }
}
