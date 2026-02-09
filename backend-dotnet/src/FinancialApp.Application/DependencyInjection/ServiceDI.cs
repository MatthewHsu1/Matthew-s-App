using FinancialApp.Application.Interfaces;
using FinancialApp.Application.Services;
using Microsoft.Extensions.DependencyInjection;

namespace FinancialApp.Application.DependencyInjection
{
    internal static class ServiceDI
    {
        public static IServiceCollection AddServices(this IServiceCollection service)
        {
            service.AddScoped<ITechnicalIndicatorsService, TechnicalIndicatorsService>();

            return service;
        }
    }
}
