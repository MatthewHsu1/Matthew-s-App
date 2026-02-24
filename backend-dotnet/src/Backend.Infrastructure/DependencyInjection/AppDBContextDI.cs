using Backend.Domain.Options.Supabase;
using Backend.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Backend.Infrastructure.DependencyInjection
{
    internal static class AppDBContextDI
    {
        private const int MaxRetryCount = 5;

        private static readonly TimeSpan MaxRetryDelay = TimeSpan.FromSeconds(30);

        public static IServiceCollection AddAppDBContext(this IServiceCollection services)
        {
            services.AddDbContextFactory<AppDbContext>((sp, options) =>
            {
                var supabaseOptions = sp.GetRequiredService<IOptions<SupabaseOptions>>().Value;

                options.UseNpgsql(supabaseOptions.DefaultConnection, npgsql =>
                    npgsql.EnableRetryOnFailure(
                        maxRetryCount: MaxRetryCount,
                        maxRetryDelay: MaxRetryDelay,
                        errorCodesToAdd: null));
            });

            return services;
        }
    }
}
