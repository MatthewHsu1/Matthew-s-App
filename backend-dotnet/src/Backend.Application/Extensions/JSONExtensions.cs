using System.Text.Json;

namespace Backend.Application.Extensions
{
    public static class JSONExtensions
    {
        public static readonly JsonSerializerOptions JsonOptions = new()
        {
            PropertyNameCaseInsensitive = true
        };

        public static readonly JsonSerializerOptions JsonCamelCaseOptions = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            PropertyNameCaseInsensitive = true
        };
    }
}
