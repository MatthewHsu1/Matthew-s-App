using Backend.Api.Options;

namespace Backend.Api.DependencyInjection;

internal static class OptionsDI
{
    /// <summary>
    /// Add options
    /// </summary>
    /// <param name="services">The service collection</param>
    /// <param name="configuration">The configuration</param>
    /// <returns>The service collection</returns>
    public static IServiceCollection AddOptions(this IServiceCollection services, IConfiguration configuration)
    {
        services.Configure<LokiLoggingOptions>(configuration.GetSection(LokiLoggingOptions.SectionName));

        return services;
    }
}
