using FinancialApp.Domain.Interfaces;
using FinancialApp.Infrastructure.Services.AlphaVantage;
using Microsoft.Extensions.DependencyInjection;

namespace FinancialApp.Infrastructure.DependencyInjection
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
