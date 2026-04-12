namespace Backend.Application.Models.Auth
{
    /// <summary>
    /// Lists authentication providers exposed to clients.
    /// </summary>
    public sealed class AuthenticationProviders
    {
        /// <summary>
        /// Indicates whether email/password authentication is available.
        /// </summary>
        public bool EmailPasswordEnabled { get; init; }

        /// <summary>
        /// Indicates whether Google authentication is available.
        /// </summary>
        public bool GoogleEnabled { get; init; }
    }
}
