using FinancialApp.Domain.Options.AlphaVantage;
using FinancialApp.Infrastructure.Services.AlphaVantage;
using FinancialApp.Testing.Http;
using Microsoft.Extensions.Options;
using System.Net;
using System.Text;

namespace FinancialApp.Infrastructure.Tests.AlphaVantage;

public class AlphaVantageMarketDataServiceOptionsTests
{
    [Fact]
    public async Task GetOptionChainAsync_UsesHistoricalOptionsQueryAndParsesResponse()
    {
        var payload = """
            {
              "endpoint": "Historical Options",
              "data": [
                { "contractID": "AAPL250117C00190000", "type": "call", "strike": "190", "expiration": "2025-01-17" }
              ]
            }
            """;

        var handler = new SequenceHttpMessageHandler(
        [
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(payload, Encoding.UTF8, "application/json") }
        ]);

        using var client = new HttpClient(handler) { BaseAddress = new Uri("https://www.alphavantage.co/") };

        var service = new AlphaVantageMarketDataService(
            new SingleClientFactory(client),
            Options.Create(new AlphaVantageOptions { ApiKey = "demo", BaseUrl = "https://www.alphavantage.co" }));

        var result = await service.GetOptionChainAsync("AAPL");

        var request = Assert.Single(handler.RequestUris);

        Assert.Contains("function=HISTORICAL_OPTIONS", request);
        Assert.Contains("symbol=AAPL", request);
        Assert.Contains("apikey=demo", request);

        var item = Assert.Single(result);
        Assert.Equal("AAPL250117C00190000", item.Symbol);
    }

    [Fact]
    public async Task GetOptionChainAsync_ReturnsEmptyListWhenDataMissing()
    {
        var payload = """{ "endpoint": "Historical Options" }""";

        var handler = new SequenceHttpMessageHandler(
        [
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(payload, Encoding.UTF8, "application/json") }
        ]);

        using var client = new HttpClient(handler) { BaseAddress = new Uri("https://www.alphavantage.co/") };

        var service = new AlphaVantageMarketDataService(
            new SingleClientFactory(client),
            Options.Create(new AlphaVantageOptions { ApiKey = "demo", BaseUrl = "https://www.alphavantage.co" }));

        var result = await service.GetOptionChainAsync("AAPL");

        Assert.Empty(result);
    }

    [Fact]
    public async Task GetOptionChainAsync_RetriesOnTransientServerError()
    {
        var payload = """
            {
              "endpoint": "Historical Options",
              "data": [
                { "contractID": "AAPL250117P00190000", "type": "put", "strike": "190", "expiration": "2025-01-17" }
              ]
            }
            """;

        var handler = new SequenceHttpMessageHandler(
        [
            new HttpResponseMessage(HttpStatusCode.InternalServerError),
            new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(payload, Encoding.UTF8, "application/json") }
        ]);

        using var client = new HttpClient(handler) { BaseAddress = new Uri("https://www.alphavantage.co/") };

        var service = new AlphaVantageMarketDataService(
            new SingleClientFactory(client),
            Options.Create(new AlphaVantageOptions { ApiKey = "demo", BaseUrl = "https://www.alphavantage.co" }));

        var result = await service.GetOptionChainAsync("AAPL");

        Assert.Equal(2, handler.Attempts);
        Assert.Single(result);
    }
}
