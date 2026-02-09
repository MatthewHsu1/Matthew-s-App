using FinancialApp.Application.Extensions;
using FinancialApp.Domain.Interfaces;
using FinancialApp.Domain.Models.AlphaVantage;
using FinancialApp.Domain.Models.Exception;
using FinancialApp.Domain.Models.MarketData;
using FinancialApp.Domain.Options.AlphaVantage;
using Microsoft.Extensions.Options;
using System.Globalization;
using System.Net;
using System.Text.Json;

namespace FinancialApp.Infrastructure.Services.AlphaVantage
{
    public sealed class AlphaVantageMarketDataService(IHttpClientFactory httpFactory, IOptions<AlphaVantageOptions> options) : IMarketDataService
    {
        /// <inheritdoc/>
        public async Task<StockQuote?> GetCurrentPriceAsync(string ticker, CancellationToken cancellationToken = default)
        {
            var query = new Dictionary<string, string>
            {
                ["function"] = "GLOBAL_QUOTE",
                ["symbol"] = ticker,
                ["apikey"] = options.Value.ApiKey
            };

            var uri = AlphaVantageResponseParser.BuildUri("query", query);

            using var httpClient = httpFactory.CreateClient("AlphaVantage");

            Func<Task<HttpResponseMessage>> action = async () =>
            {
                var response = await httpClient.GetAsync(uri, cancellationToken).ConfigureAwait(false);

                if (response.StatusCode == HttpStatusCode.TooManyRequests)
                    throw new TransientHttpFailureException(response.StatusCode);

                if ((int)response.StatusCode >= 500)
                    throw new TransientHttpFailureException(response.StatusCode);

                response.EnsureSuccessStatusCode();

                return response;
            };

            var response = await action.RetryAsync<HttpResponseMessage, TransientHttpFailureException>(
                retryCount: 3,
                delaySeconds: 2,
                delayProvider: attempt => TimeSpan.FromSeconds(Math.Pow(2, attempt)));

            var json = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);

            var parsed = JsonSerializer.Deserialize<GlobalQuoteResponse>(json, JSONExtensions.JsonOptions);

            if (parsed?.GlobalQuote is null)
                return null;

            var q = parsed.GlobalQuote;
            if (string.IsNullOrEmpty(q.Price) || !decimal.TryParse(q.Price, NumberStyles.Any, CultureInfo.InvariantCulture, out var price))
                return null;

            var timestamp = DateTime.UtcNow;
            if (DateTime.TryParse(q.LatestTradingDay, CultureInfo.InvariantCulture, DateTimeStyles.None, out var latestDay))
                timestamp = latestDay;

            return new StockQuote
            {
                Ticker = q.Symbol ?? ticker,
                Price = price,
                PreviousClose = AlphaVantageResponseParser.ParseDecimal(q.PreviousClose),
                Change = AlphaVantageResponseParser.ParseDecimal(q.Change),
                ChangePercent = AlphaVantageResponseParser.ParseChangePercent(q.ChangePercent),
                Volume = AlphaVantageResponseParser.ParseLong(q.Volume),
                Timestamp = timestamp
            };
        }

        public async Task<IReadOnlyList<OhlcvBar>> GetHistoricalPricesAsync(
            string ticker,
            DateTime from,
            DateTime to,
            string? interval = "1D",
            CancellationToken cancellationToken = default)
        {
            string function;
            string responseKey;

            switch (interval?.ToUpperInvariant())
            {
                case "1W":
                    function = "TIME_SERIES_WEEKLY";
                    responseKey = "Weekly Time Series";
                    break;
                case "1M":
                    function = "TIME_SERIES_MONTHLY";
                    responseKey = "Monthly Time Series";
                    break;
                default:
                    function = "TIME_SERIES_DAILY";
                    responseKey = "Time Series (Daily)";
                    break;
            }

            var outputSize = "compact";

            if (function == "TIME_SERIES_DAILY" && (to.Date - from.Date).TotalDays > 100)
                outputSize = "full";

            var query = new Dictionary<string, string>
            {
                ["function"] = function,
                ["symbol"] = ticker,
                ["apikey"] = options.Value.ApiKey,
                ["outputsize"] = outputSize
            };

            var uri = AlphaVantageResponseParser.BuildUri("query", query);

            using var httpClient = httpFactory.CreateClient("AlphaVantage");

            Func<Task<HttpResponseMessage>> action = async () =>
            {
                var response = await httpClient.GetAsync(uri, cancellationToken).ConfigureAwait(false);

                if (response.StatusCode == HttpStatusCode.TooManyRequests)
                    throw new TransientHttpFailureException(response.StatusCode);

                if ((int)response.StatusCode >= 500)
                    throw new TransientHttpFailureException(response.StatusCode);

                response.EnsureSuccessStatusCode();

                return response;
            };

            var response = await action.RetryAsync<HttpResponseMessage, TransientHttpFailureException>(
                retryCount: 3,
                delaySeconds: 2,
                delayProvider: attempt => TimeSpan.FromSeconds(Math.Pow(2, attempt)));

            var json = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);

            List<OhlcvBar> bars;
            if (responseKey == "Time Series (Daily)")
            {
                var parsed = JsonSerializer.Deserialize<TimeSeriesDailyResponse>(json, JSONExtensions.JsonOptions);
                bars = AlphaVantageResponseParser.ParseDailyBars(parsed?.TimeSeriesDaily);
            }
            else
            {
                bars = AlphaVantageResponseParser.ParseTimeSeriesBars(json, responseKey);
            }

            var fromDate = from.Date;
            var toDate = to.Date;

            return bars
                .Where(b => b.Date >= fromDate && b.Date <= toDate)
                .OrderBy(b => b.Date)
                .ToList();
        }
    }
}
