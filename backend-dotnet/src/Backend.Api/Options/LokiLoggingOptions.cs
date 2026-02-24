namespace Backend.Api.Options;

/// <summary>
/// Loki logging options
/// </summary>
public sealed class LokiLoggingOptions
{
    /// <summary>
    /// The section name for the Loki logging options
    /// </summary>
    public const string SectionName = "Loki";

    /// <summary>
    /// Whether the Loki logging is enabled
    /// </summary>
    public bool Enabled { get; set; }

    /// <summary>
    /// The URI of the Loki logging
    /// </summary>
    public string? Uri { get; set; }

    /// <summary>
    /// The username for the Loki logging
    /// </summary>
    public string? Username { get; set; }

    /// <summary>
    /// The password for the Loki logging
    /// </summary>
    public string? Password { get; set; }

    /// <summary>
    /// Whether the Loki logging has the required settings
    /// </summary>
    public bool HasRequiredSettings()
    {
        if (!Enabled)
        {
            return false;
        }

        return !string.IsNullOrWhiteSpace(Uri)
            && !string.IsNullOrWhiteSpace(Username)
            && !string.IsNullOrWhiteSpace(Password);
    }
}
