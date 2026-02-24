using Backend.Api.Options;

namespace Backend.Api.Tests.Options;

public sealed class LokiLoggingOptionsTests
{
    [Fact]
    public void HasRequiredSettings_ReturnsFalse_WhenEnabledAndUriMissing()
    {
        var options = new LokiLoggingOptions
        {
            Enabled = true,
            Username = "123456",
            Password = "secret"
        };

        Assert.False(options.HasRequiredSettings());
    }

    [Fact]
    public void HasRequiredSettings_ReturnsFalse_WhenEnabledAndUsernameMissing()
    {
        var options = new LokiLoggingOptions
        {
            Enabled = true,
            Uri = "https://logs-prod-us-central1.grafana.net/loki/api/v1/push",
            Password = "secret"
        };

        Assert.False(options.HasRequiredSettings());
    }

    [Fact]
    public void HasRequiredSettings_ReturnsTrue_WhenEnabledAndAllValuesProvided()
    {
        var options = new LokiLoggingOptions
        {
            Enabled = true,
            Uri = "https://logs-prod-us-central1.grafana.net/loki/api/v1/push",
            Username = "123456",
            Password = "secret"
        };

        Assert.True(options.HasRequiredSettings());
    }
}
