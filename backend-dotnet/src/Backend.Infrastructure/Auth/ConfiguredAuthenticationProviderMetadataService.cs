using Backend.Application.Interfaces;
using Backend.Application.Models.Auth;
using Backend.Domain.Options.Auth;
using Microsoft.Extensions.Options;

namespace Backend.Infrastructure.Auth
{
    /// <inheritdoc />
    internal sealed class ConfiguredAuthenticationProviderMetadataService(
        IOptions<AuthProvidersOptions> options) : IAuthenticationProviderMetadataService
    {
        /// <inheritdoc />
        public AuthenticationProviders GetProviders()
        {
            var value = options.Value;
            return new AuthenticationProviders
            {
                EmailPasswordEnabled = value.EmailPasswordEnabled,
                GoogleEnabled = value.GoogleEnabled
            };
        }
    }
}
