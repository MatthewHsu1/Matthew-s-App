using Backend.Domain.Options.AlphaVantage;
using Backend.Domain.Options.Redis;
using Backend.Domain.Options.Supabase;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.Infrastructure.DependencyInjection
{
    internal static class OptionsDI
    {
        public static IServiceCollection AddOptions(this IServiceCollection services, IConfiguration configuration)
        {
            services.Configure<AlphaVantageOptions>(configuration.GetSection(AlphaVantageOptions.SectionName));

            services.Configure<RedisOptions>(configuration.GetSection(RedisOptions.SectionName));

            services.Configure<SupabaseOptions>(configuration.GetSection(SupabaseOptions.SectionName));

            return services;
        }
    }
}
