using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.Application.DependencyInjection;

public static class ApplicationDI
{
    public static IServiceCollection AddApplication(this IServiceCollection service, IConfiguration config)
    {
        service.AddOptions(config);

        service.AddServices();

        return service;
    }
}
