using Backend.Application.Models.Auth;

namespace Backend.Application.Interfaces
{
    /// <summary>
    /// Provides access to the currently authenticated user from the active request context.
    /// </summary>
    public interface IAuthenticatedUserAccessor
    {
        /// <summary>
        /// Gets the current authenticated user, or <c>null</c> when the request is anonymous.
        /// </summary>
        /// <returns>The normalized authenticated user, or <c>null</c>.</returns>
        AuthenticatedUser? GetCurrentUser();
    }
}
