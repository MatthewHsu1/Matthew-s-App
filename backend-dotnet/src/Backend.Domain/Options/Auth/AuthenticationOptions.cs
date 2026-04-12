using System.ComponentModel.DataAnnotations;

namespace Backend.Domain.Options.Auth
{
    /// <summary>
    /// JWT authentication options for validating external identity provider tokens.
    /// </summary>
    public sealed class AuthenticationOptions
    {
        /// <summary>
        /// Configuration section name.
        /// </summary>
        public const string SectionName = "Authentication";

        /// <summary>
        /// OpenID Connect authority URL used to resolve signing keys through JWKS.
        /// </summary>
        [Required]
        public string Authority { get; set; } = string.Empty;

        /// <summary>
        /// Expected audience claim for API access tokens.
        /// </summary>
        [Required]
        public string Audience { get; set; } = string.Empty;

        /// <summary>
        /// Whether HTTPS metadata is required when loading the OpenID Connect metadata document.
        /// </summary>
        public bool RequireHttpsMetadata { get; set; } = true;

        /// <summary>
        /// Lifetime validation clock skew in seconds.
        /// </summary>
        [Range(0, 600)]
        public int ClockSkewSeconds { get; set; } = 60;
    }
}
