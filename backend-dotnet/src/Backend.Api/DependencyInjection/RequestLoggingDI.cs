using Serilog;

namespace Backend.Api.DependencyInjection;

internal static class RequestLoggingDI
{
    /// <summary>
    /// Use structured HTTP request logging
    /// </summary>
    /// <param name="app">The web application</param>
    /// <returns>The web application</returns>
    public static WebApplication UseStructuredHttpRequestLogging(this WebApplication app)
    {
        app.UseSerilogRequestLogging(options =>
        {
            options.MessageTemplate = "HTTP {RequestMethod} {RequestPath} responded {StatusCode} in {Elapsed:0.0000} ms";
            options.EnrichDiagnosticContext = (diagnosticContext, httpContext) =>
            {
                diagnosticContext.Set("RequestHost", httpContext.Request.Host.Value ?? string.Empty);
                diagnosticContext.Set("RequestScheme", httpContext.Request.Scheme);
                diagnosticContext.Set("TraceId", System.Diagnostics.Activity.Current?.TraceId.ToString() ?? httpContext.TraceIdentifier);

                var spanId = System.Diagnostics.Activity.Current?.SpanId.ToString();
                if (!string.IsNullOrWhiteSpace(spanId))
                {
                    diagnosticContext.Set("SpanId", spanId);
                }
            };
        });

        return app;
    }
}
