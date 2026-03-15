namespace Backend.Api.Contracts.Auth;

/// <summary>
/// Response payload describing the authenticated user from the current bearer token.
/// </summary>
public sealed class AuthMeResponse
{
    /// <summary>
    /// Token subject identifier.
    /// </summary>
    public required string UserId { get; init; }

    /// <summary>
    /// Token email claim when available.
    /// </summary>
    public string? Email { get; init; }

    /// <summary>
    /// Resolved identity provider for the user token.
    /// </summary>
    public string? Provider { get; init; }

    /// <summary>
    /// Raw claims from the access token grouped by claim type.
    /// </summary>
    public required IReadOnlyDictionary<string, IReadOnlyCollection<string>> Claims { get; init; }
}
