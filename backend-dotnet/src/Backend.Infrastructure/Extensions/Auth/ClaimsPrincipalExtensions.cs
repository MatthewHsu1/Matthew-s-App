using System.Security.Claims;
using Backend.Infrastructure.Extensions.Json;

namespace Backend.Infrastructure.Extensions.Auth
{
    /// <summary>
    /// Provides authentication claim helpers for provider resolution.
    /// </summary>
    internal static class ClaimsPrincipalExtensions
    {
        /// <summary>
        /// Resolves provider information from Supabase-authenticated claims.
        /// </summary>
        /// <param name="principal">Claims principal to inspect.</param>
        /// <returns>The provider identifier when available; otherwise <c>null</c>.</returns>
        internal static string? ResolveSupabaseProvider(this ClaimsPrincipal principal)
        {
            var directProvider = principal.FindFirst("app_metadata.provider")?.Value ?? principal.FindFirst("provider")?.Value;
            if (!string.IsNullOrWhiteSpace(directProvider))
            {
                return directProvider;
            }

            var appMetadata = principal.FindFirst("app_metadata")?.Value;
            if (!string.IsNullOrWhiteSpace(appMetadata)
                && JsonDocumentExtensions.TryReadStringProperty(appMetadata, "provider", out var providerFromAppMetadata))
            {
                return providerFromAppMetadata;
            }

            var identities = principal.FindFirst("identities")?.Value;
            if (!string.IsNullOrWhiteSpace(identities)
                && JsonDocumentExtensions.TryReadFirstArrayObjectProperty(identities, "provider", out var providerFromIdentities))
            {
                return providerFromIdentities;
            }

            return principal.FindFirst("amr")?.Value;
        }
    }
}
