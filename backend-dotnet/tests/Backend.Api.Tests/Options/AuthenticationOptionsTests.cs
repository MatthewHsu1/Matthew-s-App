using System.ComponentModel.DataAnnotations;
using Backend.Domain.Options.Auth;

namespace Backend.Api.Tests.Options;

public sealed class AuthenticationOptionsTests
{
    [Fact]
    public void DataAnnotationsValidation_Fails_WhenAuthorityAndAudienceMissing()
    {
        var options = new AuthenticationOptions
        {
            Authority = string.Empty,
            Audience = string.Empty
        };

        var context = new ValidationContext(options);
        var results = new List<ValidationResult>();
        var isValid = Validator.TryValidateObject(options, context, results, true);

        Assert.False(isValid);
        Assert.Contains(results, result => result.MemberNames.Contains(nameof(AuthenticationOptions.Authority)));
        Assert.Contains(results, result => result.MemberNames.Contains(nameof(AuthenticationOptions.Audience)));
    }

    [Fact]
    public void DataAnnotationsValidation_Fails_WhenClockSkewIsNegative()
    {
        var options = new AuthenticationOptions
        {
            Authority = "https://auth.example.com",
            Audience = "financial-app-api",
            ClockSkewSeconds = -1
        };

        var context = new ValidationContext(options);
        var results = new List<ValidationResult>();
        var isValid = Validator.TryValidateObject(options, context, results, true);

        Assert.False(isValid);
        Assert.Contains(results, result => result.MemberNames.Contains(nameof(AuthenticationOptions.ClockSkewSeconds)));
    }
}
