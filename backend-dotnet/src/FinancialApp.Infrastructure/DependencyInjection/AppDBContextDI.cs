using FinancialApp.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace FinancialApp.Infrastructure.DependencyInjection
{
    public static class AppDBContextDI
    {
        public static IServiceCollection AddAppDBContext(this IServiceCollection services, IConfiguration config)
        {
            var connectionString = config.GetConnectionString("DefaultConnection");

            services.AddDbContextFactory<AppDbContext>(options =>
                options.UseNpgsql(connectionString)
            );

            return services;
        }
    }
}