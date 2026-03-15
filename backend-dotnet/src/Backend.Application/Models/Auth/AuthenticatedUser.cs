namespace Backend.Application.Models.Auth
{
    /// <summary>
    /// Normalized representation of an authenticated API user.
    /// </summary>
    public sealed class AuthenticatedUser
    {
        /// <summary>
        /// Subject identifier from the access token.
        /// </summary>
        public required string UserId { get; init; }

        /// <summary>
        /// Email address claim from the access token when available.
        /// </summary>
        public string? Email { get; init; }

        /// <summary>
        /// Resolved identity provider for the current token.
        /// </summary>
        public string? Provider { get; init; }

        /// <summary>
        /// Raw claim values indexed by claim type for diagnostics.
        /// </summary>
        public required IReadOnlyDictionary<string, IReadOnlyCollection<string>> Claims { get; init; }
    }
}
