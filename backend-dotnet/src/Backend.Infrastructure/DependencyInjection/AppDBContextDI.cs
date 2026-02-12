using Backend.Domain.Options.Supabase;
using Backend.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Backend.Infrastructure.DependencyInjection
{
    internal static class AppDBContextDI
    {
        public static IServiceCollection AddAppDBContext(this IServiceCollection services)
        {
            services.AddDbContextFactory<AppDbContext>((sp, options) =>
            {
                var supabaseOptions = sp.GetRequiredService<IOptions<SupabaseOptions>>().Value;
                options.UseNpgsql(supabaseOptions.ConnectionString);
            });

            return services;
        }
    }
}