using FinancialApp.Domain.Models.AlphaVantage;
using FinancialApp.Domain.Models.MarketData;
using System.Globalization;
using System.Text.Json;
using System.Web;

namespace FinancialApp.Infrastructure.Services.AlphaVantage
{
    /// <summary>
    /// Static helper for parsing Alpha Vantage API responses into domain types.
    /// </summary>
    internal static class AlphaVantageResponseParser
    {
        public static List<OhlcvBar> ParseDailyBars(Dictionary<string, DailyBarDto>? timeSeries)
        {
            if (timeSeries is null || timeSeries.Count == 0)
                return [];

            var list = new List<OhlcvBar>(timeSeries.Count);

            foreach (var kv in timeSeries)
            {
                if (!DateTime.TryParse(kv.Key, CultureInfo.InvariantCulture, DateTimeStyles.None, out var date))
                    continue;

                var d = kv.Value;
                if (d?.Open is null || d.High is null || d.Low is null || d.Close is null)
                    continue;

                if (!decimal.TryParse(d.Open, NumberStyles.Any, CultureInfo.InvariantCulture, out var open) ||
                    !decimal.TryParse(d.High, NumberStyles.Any, CultureInfo.InvariantCulture, out var high) ||
                    !decimal.TryParse(d.Low, NumberStyles.Any, CultureInfo.InvariantCulture, out var low) ||
                    !decimal.TryParse(d.Close, NumberStyles.Any, CultureInfo.InvariantCulture, out var close))
                    continue;

                list.Add(new OhlcvBar
                {
                    Date = date,
                    Time = null,
                    Open = open,
                    High = high,
                    Low = low,
                    Close = close,
                    Volume = ParseLong(d.Volume)
                });
            }

            return list;
        }

        public static List<OhlcvBar> ParseTimeSeriesBars(string json, string responseKey)
        {
            using var doc = JsonDocument.Parse(json);

            if (!doc.RootElement.TryGetProperty(responseKey, out var series) || series.ValueKind != JsonValueKind.Object)
                return [];

            var list = new List<OhlcvBar>();

            foreach (var prop in series.EnumerateObject())
            {
                if (!DateTime.TryParse(prop.Name, CultureInfo.InvariantCulture, DateTimeStyles.None, out var date))
                    continue;

                var o = prop.Value.GetProperty("1. open").GetString();
                var h = prop.Value.GetProperty("2. high").GetString();
                var l = prop.Value.GetProperty("3. low").GetString();
                var c = prop.Value.GetProperty("4. close").GetString();
                var v = prop.Value.GetProperty("5. volume").GetString();

                if (string.IsNullOrEmpty(o) || string.IsNullOrEmpty(h) || string.IsNullOrEmpty(l) || string.IsNullOrEmpty(c))
                    continue;

                if (!decimal.TryParse(o, NumberStyles.Any, CultureInfo.InvariantCulture, out var open) ||
                    !decimal.TryParse(h, NumberStyles.Any, CultureInfo.InvariantCulture, out var high) ||
                    !decimal.TryParse(l, NumberStyles.Any, CultureInfo.InvariantCulture, out var low) ||
                    !decimal.TryParse(c, NumberStyles.Any, CultureInfo.InvariantCulture, out var close))
                    continue;

                list.Add(new OhlcvBar
                {
                    Date = date,
                    Time = null,
                    Open = open,
                    High = high,
                    Low = low,
                    Close = close,
                    Volume = ParseLong(v)
                });
            }

            return list;
        }

        public static string BuildUri(string path, Dictionary<string, string> query)
        {
            var builder = new UriBuilder();
            var queryString = string.Join("&", query.Select(kv => $"{HttpUtility.UrlEncode(kv.Key)}={HttpUtility.UrlEncode(kv.Value)}"));
            builder.Query = queryString;
            builder.Path = path;
            return builder.Uri!.ToString();
        }

        public static decimal? ParseDecimal(string? s)
        {
            if (string.IsNullOrWhiteSpace(s)) return null;
            return decimal.TryParse(s.Trim().TrimEnd('%'), NumberStyles.Any, CultureInfo.InvariantCulture, out var v) ? v : null;
        }

        public static decimal? ParseChangePercent(string? s)
        {
            if (string.IsNullOrWhiteSpace(s)) return null;
            var cleaned = s.Trim().TrimEnd('%');
            return decimal.TryParse(cleaned, NumberStyles.Any, CultureInfo.InvariantCulture, out var v) ? v : null;
        }

        public static long ParseLong(string? s)
        {
            if (string.IsNullOrWhiteSpace(s)) return 0;
            return long.TryParse(s, NumberStyles.Any, CultureInfo.InvariantCulture, out var v) ? v : 0;
        }

        public static IReadOnlyList<OptionContractSummary> ParseOptionContracts(IEnumerable<HistoricalOptionsContractDto>? contracts)
        {
            if (contracts is null)
                return [];

            var parsed = new List<OptionContractSummary>();
            var seenSymbols = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (var contract in contracts)
            {
                if (contract is null || string.IsNullOrWhiteSpace(contract.ContractId))
                    continue;

                if (!TryParseOptionType(contract.Type, out var type))
                    continue;

                if (!decimal.TryParse(contract.Strike, NumberStyles.Any, CultureInfo.InvariantCulture, out var strike))
                    continue;

                if (!DateOnly.TryParse(contract.Expiration, CultureInfo.InvariantCulture, DateTimeStyles.None, out var expiration))
                    continue;

                if (!seenSymbols.Add(contract.ContractId))
                    continue;

                parsed.Add(new OptionContractSummary
                {
                    Symbol = contract.ContractId,
                    Type = type,
                    Strike = strike,
                    Expiration = expiration
                });
            }

            return parsed
                .OrderBy(c => c.Expiration)
                .ThenBy(c => c.Strike)
                .ThenBy(c => c.Type)
                .ToList();
        }

        private static bool TryParseOptionType(string? rawType, out OptionContractType type)
        {
            if (string.Equals(rawType, "call", StringComparison.OrdinalIgnoreCase))
            {
                type = OptionContractType.Call;
                return true;
            }

            if (string.Equals(rawType, "put", StringComparison.OrdinalIgnoreCase))
            {
                type = OptionContractType.Put;
                return true;
            }

            type = default;
            return false;
        }
    }
}
