using Backend.Application.Interfaces;
using Backend.Application.Models.Auth;
using Microsoft.AspNetCore.Http;

namespace Backend.Infrastructure.Auth
{
    /// <inheritdoc />
    internal sealed class HttpContextAuthenticatedUserAccessor(
        IHttpContextAccessor httpContextAccessor,
        SupabaseJwtClaimsMapper claimsMapper) : IAuthenticatedUserAccessor
    {
        /// <inheritdoc />
        public AuthenticatedUser? GetCurrentUser()
        {
            var principal = httpContextAccessor.HttpContext?.User;
            if (principal is null)
            {
                return null;
            }

            return claimsMapper.Map(principal);
        }
    }
}
