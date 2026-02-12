using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace FinancialApp.Infrastructure.DependencyInjection
{
    public static class InfrastructureDI
    {
        public static IServiceCollection AddInfrastructure(this IServiceCollection services, IConfiguration config)
        {
            services.AddAppDBContext();

            services.AddRepository();

            services.AddServices();

            services.AddOptions(config);

            services.AddRateLimiting();

            services.AddDistributedCache(config);

            return services;
        }
    }
}