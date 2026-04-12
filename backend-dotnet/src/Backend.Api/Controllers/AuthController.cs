using Backend.Api.Contracts.Auth;
using Backend.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Api.Controllers;

[ApiController]
[Route("api/auth")]
public sealed class AuthController(
    IAuthenticatedUserAccessor authenticatedUserAccessor,
    IAuthenticationProviderMetadataService providerMetadataService) : ControllerBase
{
    [HttpGet("me")]
    [ProducesResponseType(typeof(AuthMeResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public IActionResult GetMe()
    {
        var user = authenticatedUserAccessor.GetCurrentUser();
        if (user is null)
        {
            return Unauthorized();
        }

        return Ok(new AuthMeResponse
        {
            UserId = user.UserId,
            Email = user.Email,
            Provider = user.Provider,
            Claims = user.Claims
        });
    }

    [AllowAnonymous]
    [HttpGet("providers")]
    [ProducesResponseType(typeof(AuthProvidersResponse), StatusCodes.Status200OK)]
    public IActionResult GetProviders()
    {
        var providers = providerMetadataService.GetProviders();
        return Ok(new AuthProvidersResponse
        {
            EmailPasswordEnabled = providers.EmailPasswordEnabled,
            GoogleEnabled = providers.GoogleEnabled
        });
    }
}
