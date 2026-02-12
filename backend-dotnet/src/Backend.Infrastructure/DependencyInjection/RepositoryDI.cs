using Backend.Infrastructure.Repositories;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.Infrastructure.DependencyInjection
{
    internal static class RepositoryDI
    {
        public static IServiceCollection AddRepository(this IServiceCollection services)
        {
            services.AddScoped<IEulerpoolRepository, EulerpoolRepository>();

            return services;
        }
    }
}