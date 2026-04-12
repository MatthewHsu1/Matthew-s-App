using Backend.Application.Interfaces;
using Backend.Domain.Interfaces;
using Backend.Infrastructure.Auth;
using Backend.Infrastructure.Services.AlphaVantage;
using Backend.Infrastructure.Services.Indicators;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.Infrastructure.DependencyInjection
{
    internal static class ServiceDI
    {
        public static IServiceCollection AddServices(this IServiceCollection service)
        {
            service.AddScoped<IMarketDataService, AlphaVantageMarketDataService>();
            service.AddScoped<ITechnicalIndicatorCalculator, SkenderTechnicalIndicatorCalculator>();
            service.AddScoped<IAuthenticatedUserAccessor, HttpContextAuthenticatedUserAccessor>();
            service.AddScoped<IAuthenticationProviderMetadataService, ConfiguredAuthenticationProviderMetadataService>();
            service.AddSingleton<SupabaseJwtClaimsMapper>();

            return service;
        }
    }
}
