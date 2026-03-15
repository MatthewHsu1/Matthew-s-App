using Backend.Infrastructure.Extensions.Json;

namespace Backend.Infrastructure.Tests.Extensions.Json;

public sealed class JsonDocumentExtensionsTests
{
    [Fact]
    public void TryReadStringProperty_ReturnsTrue_WhenPropertyExistsAsString()
    {
        var result = JsonDocumentExtensions.TryReadStringProperty("""{"provider":"google"}""", "provider", out var value);

        Assert.True(result);
        Assert.Equal("google", value);
    }

    [Fact]
    public void TryReadStringProperty_ReturnsFalse_WhenPropertyIsMissing()
    {
        var result = JsonDocumentExtensions.TryReadStringProperty("""{"role":"user"}""", "provider", out var value);

        Assert.False(result);
        Assert.Null(value);
    }

    [Fact]
    public void TryReadFirstArrayObjectProperty_ReturnsTrue_WhenFirstObjectContainsStringProperty()
    {
        var result = JsonDocumentExtensions.TryReadFirstArrayObjectProperty("""[{"provider":"azure"}]""", "provider", out var value);

        Assert.True(result);
        Assert.Equal("azure", value);
    }

    [Fact]
    public void TryReadFirstArrayObjectProperty_ReturnsFalse_WhenArrayIsEmpty()
    {
        var result = JsonDocumentExtensions.TryReadFirstArrayObjectProperty("[]", "provider", out var value);

        Assert.False(result);
        Assert.Null(value);
    }

    [Fact]
    public void TryReadStringProperty_ReturnsFalse_WhenJsonIsInvalid()
    {
        var result = JsonDocumentExtensions.TryReadStringProperty("{invalid-json", "provider", out var value);

        Assert.False(result);
        Assert.Null(value);
    }
}
