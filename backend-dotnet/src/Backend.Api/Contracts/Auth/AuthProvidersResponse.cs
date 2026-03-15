namespace Backend.Api.Contracts.Auth;

/// <summary>
/// Response payload listing available authentication providers.
/// </summary>
public sealed class AuthProvidersResponse
{
    /// <summary>
    /// Indicates whether email and password authentication is enabled.
    /// </summary>
    public bool EmailPasswordEnabled { get; init; }

    /// <summary>
    /// Indicates whether Google OAuth authentication is enabled.
    /// </summary>
    public bool GoogleEnabled { get; init; }
}
