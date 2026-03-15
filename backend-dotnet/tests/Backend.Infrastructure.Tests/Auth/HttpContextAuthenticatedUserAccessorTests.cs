using System.Security.Claims;
using Backend.Infrastructure.Auth;
using Microsoft.AspNetCore.Http;

namespace Backend.Infrastructure.Tests.Auth;

public sealed class HttpContextAuthenticatedUserAccessorTests
{
    [Fact]
    public void GetCurrentUser_ReturnsNull_WhenPrincipalIsAnonymous()
    {
        var contextAccessor = new HttpContextAccessor
        {
            HttpContext = new DefaultHttpContext()
        };
        var sut = new HttpContextAuthenticatedUserAccessor(contextAccessor, new SupabaseJwtClaimsMapper());

        var user = sut.GetCurrentUser();

        Assert.Null(user);
    }

    [Fact]
    public void GetCurrentUser_ReturnsMappedUser_WhenPrincipalIsAuthenticated()
    {
        var context = new DefaultHttpContext();
        context.User = new ClaimsPrincipal(
            new ClaimsIdentity(
            [
                new Claim("sub", "user-456"),
                new Claim("email", "wheel@example.com"),
                new Claim("provider", "email")
            ],
                authenticationType: "Bearer"));

        var contextAccessor = new HttpContextAccessor { HttpContext = context };
        var sut = new HttpContextAuthenticatedUserAccessor(contextAccessor, new SupabaseJwtClaimsMapper());

        var user = sut.GetCurrentUser();

        Assert.NotNull(user);
        Assert.Equal("user-456", user.UserId);
        Assert.Equal("wheel@example.com", user.Email);
        Assert.Equal("email", user.Provider);
    }
}
