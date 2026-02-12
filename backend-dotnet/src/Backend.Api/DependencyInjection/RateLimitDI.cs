using Microsoft.AspNetCore.RateLimiting;
using System.Threading.RateLimiting;

namespace Backend.Api.DependencyInjection
{
    internal static class RateLimitDI
    {
        public static IServiceCollection AddRateLimiting(this IServiceCollection services)
        {
            services.AddRateLimiter(options =>
            {
                options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;

                // Global policy: 100 requests per minute per IP
                options.AddFixedWindowLimiter("fixed", policyOptions =>
                {
                    policyOptions.PermitLimit = 100;
                    policyOptions.Window = TimeSpan.FromMinutes(1);
                    policyOptions.QueueProcessingOrder = QueueProcessingOrder.OldestFirst;
                    policyOptions.QueueLimit = 0;
                });

                // Stricter policy for auth/market-data endpoints (example)
                options.AddFixedWindowLimiter("strict", policyOptions =>
                {
                    policyOptions.PermitLimit = 20;
                    policyOptions.Window = TimeSpan.FromMinutes(1);
                    policyOptions.QueueProcessingOrder = QueueProcessingOrder.OldestFirst;
                    policyOptions.QueueLimit = 0;
                });
            });

            return services;
        }
    }
}
