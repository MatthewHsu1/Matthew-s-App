using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Headers;
using System.Security.Claims;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.IdentityModel.Protocols.OpenIdConnect;
using Microsoft.IdentityModel.Tokens;

namespace Backend.Api.Tests.Auth;

public sealed class AuthEndpointsTests : IClassFixture<AuthEndpointsTests.TestApiFactory>
{
    private readonly HttpClient _client;
    private readonly SymmetricSecurityKey _signingKey;

    public AuthEndpointsTests(TestApiFactory factory)
    {
        _client = factory.CreateClient();
        _signingKey = factory.SigningKey;
    }

    [Fact]
    public async Task GetMe_ReturnsUnauthorized_WhenNoBearerToken()
    {
        var response = await _client.GetAsync("/api/auth/me");

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetProviders_ReturnsOk_WhenAnonymous()
    {
        var response = await _client.GetAsync("/api/auth/providers");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var payload = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync());
        Assert.True(payload.RootElement.GetProperty("emailPasswordEnabled").GetBoolean());
        Assert.True(payload.RootElement.GetProperty("googleEnabled").GetBoolean());
    }

    [Fact]
    public async Task WheelStateEndpoint_ReturnsUnauthorized_WhenNoBearerToken()
    {
        var response = await _client.GetAsync("/api/wheel-state/SPY");

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetMe_ReturnsOk_WhenTokenIsValid()
    {
        var response = await SendAuthorizedRequestAsync(
            "/api/auth/me",
            CreateToken("https://auth.test.local", "financial-app-api", DateTime.UtcNow.AddMinutes(5)));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var payload = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync());
        Assert.Equal("user-123", payload.RootElement.GetProperty("userId").GetString());
        Assert.Equal("trader@example.com", payload.RootElement.GetProperty("email").GetString());
        Assert.Equal("google", payload.RootElement.GetProperty("provider").GetString());
    }

    [Fact]
    public async Task GetMe_ReturnsUnauthorized_WhenIssuerIsInvalid()
    {
        var response = await SendAuthorizedRequestAsync(
            "/api/auth/me",
            CreateToken("https://invalid-issuer.test", "financial-app-api", DateTime.UtcNow.AddMinutes(5)));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetMe_ReturnsUnauthorized_WhenAudienceIsInvalid()
    {
        var response = await SendAuthorizedRequestAsync(
            "/api/auth/me",
            CreateToken("https://auth.test.local", "wrong-audience", DateTime.UtcNow.AddMinutes(5)));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetMe_ReturnsUnauthorized_WhenTokenExpiredBeyondClockSkew()
    {
        var response = await SendAuthorizedRequestAsync(
            "/api/auth/me",
            CreateToken("https://auth.test.local", "financial-app-api", DateTime.UtcNow.AddMinutes(-5)));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetMe_ReturnsOk_WhenTokenExpiredWithinClockSkew()
    {
        var response = await SendAuthorizedRequestAsync(
            "/api/auth/me",
            CreateToken("https://auth.test.local", "financial-app-api", DateTime.UtcNow.AddSeconds(-30)));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    private string CreateToken(string issuer, string audience, DateTime expiresUtc)
    {
        var descriptor = new SecurityTokenDescriptor
        {
            Issuer = issuer,
            Audience = audience,
            NotBefore = DateTime.UtcNow.AddMinutes(-10),
            Expires = expiresUtc,
            Subject = new ClaimsIdentity(
            [
                new Claim(JwtRegisteredClaimNames.Sub, "user-123"),
                new Claim(JwtRegisteredClaimNames.Email, "trader@example.com"),
                new Claim("provider", "google")
            ]),
            SigningCredentials = new SigningCredentials(_signingKey, SecurityAlgorithms.HmacSha256)
        };

        var handler = new JwtSecurityTokenHandler();
        return handler.WriteToken(handler.CreateToken(descriptor));
    }

    private Task<HttpResponseMessage> SendAuthorizedRequestAsync(string path, string token)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, path);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        return _client.SendAsync(request);
    }

    public sealed class TestApiFactory : WebApplicationFactory<Program>
    {
        public SymmetricSecurityKey SigningKey { get; } =
            new(Encoding.UTF8.GetBytes("super-secret-signing-key-for-tests-only-12345"));

        protected override IHost CreateHost(IHostBuilder builder)
        {
            builder.ConfigureServices(services =>
            {
                services.PostConfigureAll<JwtBearerOptions>(options =>
                {
                    options.Authority = string.Empty;
                    options.MetadataAddress = string.Empty;
                    options.RequireHttpsMetadata = false;
                    options.Configuration = new OpenIdConnectConfiguration
                    {
                        Issuer = "https://auth.test.local"
                    };
                    options.Configuration.SigningKeys.Add(SigningKey);
                    options.TokenValidationParameters = new TokenValidationParameters
                    {
                        ValidateIssuerSigningKey = true,
                        IssuerSigningKey = SigningKey,
                        ValidateIssuer = true,
                        ValidIssuer = "https://auth.test.local",
                        ValidateAudience = true,
                        ValidAudience = "financial-app-api",
                        ValidateLifetime = true,
                        ClockSkew = TimeSpan.FromSeconds(60)
                    };
                });
            });

            return base.CreateHost(builder);
        }
    }
}
