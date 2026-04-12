namespace Backend.Domain.Options.Auth
{
    /// <summary>
    /// Feature flags describing enabled external authentication providers.
    /// </summary>
    public sealed class AuthProvidersOptions
    {
        /// <summary>
        /// Configuration section name.
        /// </summary>
        public const string SectionName = "AuthProviders";

        /// <summary>
        /// Indicates whether email/password sign in is available.
        /// </summary>
        public bool EmailPasswordEnabled { get; set; } = true;

        /// <summary>
        /// Indicates whether Google sign in is available.
        /// </summary>
        public bool GoogleEnabled { get; set; } = true;
    }
}
