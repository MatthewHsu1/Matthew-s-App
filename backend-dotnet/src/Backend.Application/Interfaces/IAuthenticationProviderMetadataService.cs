using Backend.Application.Models.Auth;

namespace Backend.Application.Interfaces
{
    /// <summary>
    /// Provides metadata about enabled authentication providers for client discovery.
    /// </summary>
    public interface IAuthenticationProviderMetadataService
    {
        /// <summary>
        /// Gets enabled authentication providers.
        /// </summary>
        /// <returns>The enabled authentication providers.</returns>
        AuthenticationProviders GetProviders();
    }
}
