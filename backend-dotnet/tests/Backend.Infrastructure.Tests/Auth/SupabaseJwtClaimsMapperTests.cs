using System.Security.Claims;
using Backend.Infrastructure.Auth;

namespace Backend.Infrastructure.Tests.Auth;

public sealed class SupabaseJwtClaimsMapperTests
{
    [Fact]
    public void Map_ReturnsNull_WhenSubjectClaimIsMissing()
    {
        var mapper = new SupabaseJwtClaimsMapper();
        var principal = new ClaimsPrincipal(
            new ClaimsIdentity(
                [new Claim("email", "trader@example.com")],
                authenticationType: "Bearer"));

        var user = mapper.Map(principal);

        Assert.Null(user);
    }

    [Fact]
    public void Map_ParsesProviderFromAppMetadataJson()
    {
        var mapper = new SupabaseJwtClaimsMapper();
        var principal = new ClaimsPrincipal(
            new ClaimsIdentity(
            [
                new Claim("sub", "user-123"),
                new Claim("email", "trader@example.com"),
                new Claim("app_metadata", """{"provider":"google"}""")
            ],
                authenticationType: "Bearer"));

        var user = mapper.Map(principal);

        Assert.NotNull(user);
        Assert.Equal("user-123", user.UserId);
        Assert.Equal("trader@example.com", user.Email);
        Assert.Equal("google", user.Provider);
        Assert.True(user.Claims.ContainsKey("app_metadata"));
    }

    [Fact]
    public void Map_UsesDirectProviderClaim_WhenPresent()
    {
        var mapper = new SupabaseJwtClaimsMapper();
        var principal = new ClaimsPrincipal(
            new ClaimsIdentity(
            [
                new Claim("sub", "user-123"),
                new Claim("provider", "github"),
                new Claim("app_metadata", """{"provider":"google"}""")
            ],
                authenticationType: "Bearer"));

        var user = mapper.Map(principal);

        Assert.NotNull(user);
        Assert.Equal("github", user.Provider);
    }

    [Fact]
    public void Map_ParsesProviderFromIdentitiesJson_WhenAppMetadataProviderMissing()
    {
        var mapper = new SupabaseJwtClaimsMapper();
        var principal = new ClaimsPrincipal(
            new ClaimsIdentity(
            [
                new Claim("sub", "user-123"),
                new Claim("app_metadata", """{"role":"user"}"""),
                new Claim("identities", """[{"provider":"azure"}]""")
            ],
                authenticationType: "Bearer"));

        var user = mapper.Map(principal);

        Assert.NotNull(user);
        Assert.Equal("azure", user.Provider);
    }

    [Fact]
    public void Map_FallsBackToAmr_WhenProviderClaimsUnavailable()
    {
        var mapper = new SupabaseJwtClaimsMapper();
        var principal = new ClaimsPrincipal(
            new ClaimsIdentity(
            [
                new Claim("sub", "user-123"),
                new Claim("amr", "pwd")
            ],
                authenticationType: "Bearer"));

        var user = mapper.Map(principal);

        Assert.NotNull(user);
        Assert.Equal("pwd", user.Provider);
    }

    [Fact]
    public void Map_IgnoresMalformedJsonAndContinuesFallback()
    {
        var mapper = new SupabaseJwtClaimsMapper();
        var principal = new ClaimsPrincipal(
            new ClaimsIdentity(
            [
                new Claim("sub", "user-123"),
                new Claim("app_metadata", "{not-valid-json"),
                new Claim("identities", "[not-valid-json"),
                new Claim("amr", "otp")
            ],
                authenticationType: "Bearer"));

        var user = mapper.Map(principal);

        Assert.NotNull(user);
        Assert.Equal("otp", user.Provider);
    }
}
