using System.Text.Json;

namespace FinancialApp.Application.Extensions
{
    public static class JSONExtensions
    {
        public static readonly JsonSerializerOptions JsonOptions = new()
        {
            PropertyNameCaseInsensitive = true
        };
    }
}
