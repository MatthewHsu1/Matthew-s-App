using Backend.Api.Options;
using Microsoft.Extensions.Options;
using Serilog;
using Serilog.Debugging;
using Serilog.Sinks.Grafana.Loki;

namespace Backend.Api.DependencyInjection;

internal static class LoggingDI
{
    /// <summary>
    /// Configure structured logging
    /// </summary>
    /// <param name="builder">The web application builder</param>
    /// <returns>The web application builder</returns>
    public static WebApplicationBuilder ConfigureStructuredLogging(this WebApplicationBuilder builder)
    {
        if (builder.Environment.IsDevelopment())
        {
            SelfLog.Enable(message => Console.Error.WriteLine($"[Serilog.SelfLog] {message}"));
        }

        builder.Host.UseSerilog((context, services, loggerConfiguration) =>
        {
            var lokiOptions = services.GetRequiredService<IOptions<LokiLoggingOptions>>().Value;

            loggerConfiguration
                .ReadFrom.Configuration(context.Configuration)
                .ReadFrom.Services(services)
                .Enrich.FromLogContext()
                .Enrich.WithEnvironmentName()
                .Enrich.WithMachineName()
                .Enrich.WithThreadId()
                .WriteTo.Console();

            if (!lokiOptions.HasRequiredSettings())
            {
                if (lokiOptions.Enabled)
                {
                    Console.Error.WriteLine("Loki logging is enabled but missing Uri/Username/Password. Falling back to console logging only.");
                }

                return;
            }

            loggerConfiguration.WriteTo.GrafanaLoki(
                lokiOptions.Uri!,
                credentials: new LokiCredentials
                {
                    Login = lokiOptions.Username!,
                    Password = lokiOptions.Password!
                },
                labels:
                [
                    new LokiLabel { Key = "app", Value = "matthew's app" },
                    new LokiLabel { Key = "service", Value = "backend-api" },
                    new LokiLabel { Key = "environment", Value = context.HostingEnvironment.EnvironmentName }
                ]);
        });

        return builder;
    }
}
