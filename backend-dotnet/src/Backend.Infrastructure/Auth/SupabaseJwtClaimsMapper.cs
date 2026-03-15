using System.Security.Claims;
using Backend.Application.Models.Auth;
using Backend.Infrastructure.Extensions.Auth;

namespace Backend.Infrastructure.Auth
{
    /// <summary>
    /// Maps JWT claims into a normalized authenticated user model.
    /// </summary>
    internal sealed class SupabaseJwtClaimsMapper
    {
        /// <summary>
        /// Maps a claims principal into an authenticated user model.
        /// </summary>
        /// <param name="principal">Claims principal for the active request.</param>
        /// <returns>The normalized authenticated user, or <c>null</c> if required claims are missing.</returns>
        public AuthenticatedUser? Map(ClaimsPrincipal principal)
        {
            if (principal.Identity?.IsAuthenticated != true)
            {
                return null;
            }

            var subject = principal.FindFirst("sub")?.Value ?? principal.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrWhiteSpace(subject))
            {
                return null;
            }

            var claims = principal.Claims
                .GroupBy(claim => claim.Type)
                .ToDictionary(
                    group => group.Key,
                    group => (IReadOnlyCollection<string>)group
                        .Select(claim => claim.Value)
                        .Distinct(StringComparer.Ordinal)
                        .ToArray(),
                    StringComparer.Ordinal);

            return new AuthenticatedUser
            {
                UserId = subject,
                Email = principal.FindFirst("email")?.Value ?? principal.FindFirst(ClaimTypes.Email)?.Value,
                Provider = principal.ResolveSupabaseProvider(),
                Claims = claims
            };
        }
    }
}
