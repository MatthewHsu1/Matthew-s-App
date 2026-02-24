using Backend.Application.DependencyInjection;
using Backend.Infrastructure.DependencyInjection;

namespace Backend.Api.DependencyInjection;

public static class ApiDI
{
    /// <summary>
    /// Set up services for the project.
    /// </summary>
    /// <param name="builder">The web application builder</param>
    /// <returns>The web application builder</returns>
    public static WebApplicationBuilder AddApi(this WebApplicationBuilder builder)
    {
        var services = builder.Services;

        var config = builder.Configuration;

        builder.ConfigureStructuredLogging();

        services.AddOptions(config);

        services.AddControllers();

        services.AddOpenApi();

        services.AddRateLimiting();

        services.AddInfrastructure(config);

        services.AddApplication(config);

        return builder;
    }

    /// <summary>
    /// Set up middleware for the project.
    /// </summary>
    /// <param name="application">The web application</param>
    /// <returns>The web application</returns>
    public static WebApplication UseApi(this WebApplication application)
    {
        application.UseHttpsRedirection();

        application.UseStructuredHttpRequestLogging();

        application.UseRateLimiter();

        application.UseAuthorization();

        application.MapControllers();

        return application;
    }
}
