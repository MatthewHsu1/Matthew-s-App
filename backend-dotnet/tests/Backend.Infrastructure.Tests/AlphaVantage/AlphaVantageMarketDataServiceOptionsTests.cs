using Backend.Domain.Options.AlphaVantage;
using Backend.Infrastructure.Services.AlphaVantage;
using Backend.Testing.Http;
using Microsoft.Extensions.Options;
using System.Net;
using System.Text;

namespace Backend.Infrastructure.Tests.AlphaVantage;

public class AlphaVantageMarketDataServiceOptionsTests
{
    [Fact]
    public async Task GetOptionChainAsync_UsesHistoricalOptionsQueryAndParsesSnapshotResponse()
    {
        var quotePayload = """
            {
              "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "185.00",
                "07. latest trading day": "2025-01-15"
              }
            }
            """;

        var optionPayload = """
            {
              "endpoint": "Historical Options",
              "data": [
                {
                  "contractID": "AAPL250117C00190000",
                  "type": "call",
                  "strike": "190",
                  "expiration": "2025-01-17",
                  "bid": "1.00",
                  "ask": "1.20",
                  "last": "1.10",
                  "implied_volatility": "0.23",
                  "delta": "0.33",
                  "gamma": "0.04",
                  "theta": "-0.02",
                  "vega": "0.09"
                }
              ]
            }
            """;

        var handler = new SequenceHttpMessageHandler(
        [
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(quotePayload, Encoding.UTF8, "application/json") },
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(optionPayload, Encoding.UTF8, "application/json") }
        ]);

        using var client = new HttpClient(handler) { BaseAddress = new Uri("https://www.alphavantage.co/") };

        var service = new AlphaVantageMarketDataService(
            new SingleClientFactory(client),
            Options.Create(new AlphaVantageOptions { ApiKey = "demo", BaseUrl = "https://www.alphavantage.co" }));

        var result = await service.GetOptionChainAsync("AAPL");

        Assert.Equal(2, handler.RequestUris.Count);
        Assert.Contains(handler.RequestUris, request => request.Contains("function=GLOBAL_QUOTE"));

        var request = Assert.Single(handler.RequestUris, uri => uri.Contains("function=HISTORICAL_OPTIONS"));

        Assert.Contains("function=HISTORICAL_OPTIONS", request);
        Assert.Contains("symbol=AAPL", request);
        Assert.Contains("apikey=demo", request);

        Assert.NotNull(result);
        Assert.Equal("AAPL", result!.Ticker);
        Assert.Equal(185m, result.UnderlyingPrice);

        var item = Assert.Single(result.Contracts);
        Assert.Equal("AAPL250117C00190000", item.Symbol);
    }

    [Fact]
    public async Task GetOptionChainAsync_ReturnsEmptyContractsWhenDataMissing()
    {
        var quotePayload = """
            {
              "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "185.00",
                "07. latest trading day": "2025-01-15"
              }
            }
            """;

        var optionPayload = """{ "endpoint": "Historical Options" }""";

        var handler = new SequenceHttpMessageHandler(
        [
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(quotePayload, Encoding.UTF8, "application/json") },
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(optionPayload, Encoding.UTF8, "application/json") }
        ]);

        using var client = new HttpClient(handler) { BaseAddress = new Uri("https://www.alphavantage.co/") };

        var service = new AlphaVantageMarketDataService(
            new SingleClientFactory(client),
            Options.Create(new AlphaVantageOptions { ApiKey = "demo", BaseUrl = "https://www.alphavantage.co" }));

        var result = await service.GetOptionChainAsync("AAPL");

        Assert.NotNull(result);
        Assert.Empty(result!.Contracts);
    }

    [Fact]
    public async Task GetOptionChainAsync_RetriesOnTransientServerError()
    {
        var quotePayload = """
            {
              "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "185.00",
                "07. latest trading day": "2025-01-15"
              }
            }
            """;

        var optionPayload = """
            {
              "endpoint": "Historical Options",
              "data": [
                { "contractID": "AAPL250117P00190000", "type": "put", "strike": "190", "expiration": "2025-01-17" }
              ]
            }
            """;

        var handler = new SequenceHttpMessageHandler(
        [
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(quotePayload, Encoding.UTF8, "application/json") },
            new HttpResponseMessage(HttpStatusCode.InternalServerError),
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(optionPayload, Encoding.UTF8, "application/json") }
        ]);

        using var client = new HttpClient(handler) { BaseAddress = new Uri("https://www.alphavantage.co/") };

        var service = new AlphaVantageMarketDataService(
            new SingleClientFactory(client),
            Options.Create(new AlphaVantageOptions { ApiKey = "demo", BaseUrl = "https://www.alphavantage.co" }));

        var result = await service.GetOptionChainAsync("AAPL");

        Assert.Equal(3, handler.Attempts);
        Assert.NotNull(result);
        Assert.Single(result!.Contracts);
    }

    [Fact]
    public async Task GetOptionChainAsync_ReturnsNullWhenUnderlyingUnavailable()
    {
        var optionPayload = """
            {
              "endpoint": "Historical Options",
              "data": [
                { "contractID": "AAPL250117P00190000", "type": "put", "strike": "190", "expiration": "2025-01-17" }
              ]
            }
            """;

        var handler = new SequenceHttpMessageHandler(
        [
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("""{ "Global Quote": { "01. symbol": "AAPL" } }""", Encoding.UTF8, "application/json") },
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(optionPayload, Encoding.UTF8, "application/json") }
        ]);

        using var client = new HttpClient(handler) { BaseAddress = new Uri("https://www.alphavantage.co/") };

        var service = new AlphaVantageMarketDataService(
            new SingleClientFactory(client),
            Options.Create(new AlphaVantageOptions { ApiKey = "demo", BaseUrl = "https://www.alphavantage.co" }));

        var result = await service.GetOptionChainAsync("AAPL");

        Assert.Null(result);
    }
}
