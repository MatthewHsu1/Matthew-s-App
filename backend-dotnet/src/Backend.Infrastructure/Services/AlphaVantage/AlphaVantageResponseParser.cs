using Backend.Domain.Models.AlphaVantage;
using Backend.Domain.Models.MarketData;
using System.Globalization;
using System.Text.Json;
using System.Web;

namespace Backend.Infrastructure.Services.AlphaVantage
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

        public static OptionChainSnapshot ParseOptionChainSnapshot(
            string ticker,
            decimal underlyingPrice,
            DateTime asOf,
            IEnumerable<HistoricalOptionsContractDto>? contracts,
            PremiumBasis defaultPremiumBasis = PremiumBasis.Mid,
            decimal atmTolerancePercent = 0.5m)
        {
            var parsed = new List<OptionContractQuote>();
            var seenSymbols = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (var contract in contracts ?? [])
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

                var bid = ParseDecimal(contract.Bid);
                var ask = ParseDecimal(contract.Ask);
                var last = ParseDecimal(contract.Last);
                var impliedVolatility = ParseDecimal(contract.ImpliedVolatility);

                var delta = ParseDecimal(contract.Delta);
                var gamma = ParseDecimal(contract.Gamma);
                var theta = ParseDecimal(contract.Theta);
                var vega = ParseDecimal(contract.Vega);

                var greeks = new OptionGreeks
                {
                    Delta = delta,
                    Gamma = gamma,
                    Theta = theta,
                    Vega = vega
                };

                var hasAnyGreeks = delta.HasValue || gamma.HasValue || theta.HasValue || vega.HasValue;
                var hasCompleteGreeks = delta.HasValue && gamma.HasValue && theta.HasValue && vega.HasValue;

                var mid = ComputeMid(bid, ask);
                var premium = SelectPremium(defaultPremiumBasis, bid, ask, last, mid);

                parsed.Add(new OptionContractQuote
                {
                    Symbol = contract.ContractId,
                    Type = type,
                    Strike = strike,
                    Expiration = expiration,
                    Bid = bid,
                    Ask = ask,
                    Last = last,
                    Mid = mid,
                    SelectedPremium = premium.Value,
                    SelectedPremiumBasis = premium.Basis,
                    ImpliedVolatility = impliedVolatility,
                    Greeks = hasAnyGreeks ? greeks : null,
                    Moneyness = ComputeMoneyness(type, strike, underlyingPrice, atmTolerancePercent),
                    HasCompleteGreeks = hasCompleteGreeks,
                    SelectionEligibilityReason = hasCompleteGreeks ? null : "missing_greeks"
                });
            }

            return new OptionChainSnapshot
            {
                Ticker = ticker,
                UnderlyingPrice = underlyingPrice,
                AsOf = asOf,
                Contracts = parsed
                    .OrderBy(c => c.Expiration)
                    .ThenBy(c => c.Strike)
                    .ThenBy(c => c.Type)
                    .ThenBy(c => c.Symbol, StringComparer.OrdinalIgnoreCase)
                    .ToList()
            };
        }

        private static decimal? ComputeMid(decimal? bid, decimal? ask)
        {
            if (!bid.HasValue || !ask.HasValue || bid.Value <= 0m || ask.Value <= 0m)
                return null;

            return (bid.Value + ask.Value) / 2m;
        }

        private static (decimal? Value, PremiumBasis? Basis) SelectPremium(
            PremiumBasis defaultBasis,
            decimal? bid,
            decimal? ask,
            decimal? last,
            decimal? mid)
        {
            var ranked = defaultBasis switch
            {
                PremiumBasis.Bid => new (PremiumBasis Basis, decimal? Value)[]
                {
                    (PremiumBasis.Bid, bid), (PremiumBasis.Mid, mid), (PremiumBasis.Last, last), (PremiumBasis.Ask, ask)
                },
                PremiumBasis.Ask => new (PremiumBasis Basis, decimal? Value)[]
                {
                    (PremiumBasis.Ask, ask), (PremiumBasis.Mid, mid), (PremiumBasis.Last, last), (PremiumBasis.Bid, bid)
                },
                PremiumBasis.Last => new (PremiumBasis Basis, decimal? Value)[]
                {
                    (PremiumBasis.Last, last), (PremiumBasis.Mid, mid), (PremiumBasis.Bid, bid), (PremiumBasis.Ask, ask)
                },
                _ =>
                [
                    (PremiumBasis.Mid, mid), (PremiumBasis.Last, last), (PremiumBasis.Bid, bid), (PremiumBasis.Ask, ask)
                ]
            };

            foreach (var candidate in ranked)
            {
                if (candidate.Value.HasValue)
                    return (candidate.Value, candidate.Basis);
            }

            return (null, null);
        }

        private static OptionMoneyness ComputeMoneyness(
            OptionContractType type,
            decimal strike,
            decimal underlyingPrice,
            decimal atmTolerancePercent)
        {
            if (underlyingPrice <= 0m)
                return OptionMoneyness.ATM;

            var tolerance = underlyingPrice * (atmTolerancePercent / 100m);

            if (Math.Abs(strike - underlyingPrice) <= tolerance)
                return OptionMoneyness.ATM;

            if (type == OptionContractType.Call)
                return strike < underlyingPrice ? OptionMoneyness.ITM : OptionMoneyness.OTM;

            return strike > underlyingPrice ? OptionMoneyness.ITM : OptionMoneyness.OTM;
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
