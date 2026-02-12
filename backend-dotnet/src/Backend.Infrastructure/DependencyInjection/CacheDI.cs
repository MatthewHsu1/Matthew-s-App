using Backend.Domain.Options.Redis;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.Infrastructure.DependencyInjection
{
    internal static class CacheDI
    {
        public static IServiceCollection AddDistributedCache(this IServiceCollection services, IConfiguration configuration)
        {
            var redisOptions = new RedisOptions();
            configuration.GetSection(RedisOptions.SectionName).Bind(redisOptions);

            if (!string.IsNullOrWhiteSpace(redisOptions.Configuration))
            {
                services.AddStackExchangeRedisCache(options =>
                {
                    options.Configuration = redisOptions.Configuration;
                    options.InstanceName = redisOptions.InstanceName;
                });
            }
            else
            {
                services.AddDistributedMemoryCache();
            }

            return services;
        }
    }
}
