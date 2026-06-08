using System.Reflection;

namespace Backend.Api.Tests.Architecture;

public sealed class LayeringDependencyTests
{
    [Fact]
    public void BackendApi_DoesNotReference_BackendInfrastructure()
    {
        var dependencyNames = typeof(Backend.Api.DependencyInjection.ApiDI).Assembly
            .GetReferencedAssemblies()
            .Select(assemblyName => assemblyName.Name)
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .ToHashSet(StringComparer.Ordinal);

        Assert.DoesNotContain("Backend.Infrastructure", dependencyNames);
    }
}
