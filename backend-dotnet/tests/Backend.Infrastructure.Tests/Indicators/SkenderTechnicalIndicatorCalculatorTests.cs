using Backend.Application.Services;
using Backend.Application.DependencyInjection;
using Backend.Application.Interfaces;
using Backend.Domain.Interfaces;
using Backend.Domain.Models.MarketData;
using Backend.Infrastructure.DependencyInjection;
using Backend.Infrastructure.Services.Indicators;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.Infrastructure.Tests.Indicators;

public class SkenderTechnicalIndicatorCalculatorTests
{
    [Fact]
    public void ComputeRsi14_ReturnsNull_WhenLessThan15Bars()
    {
        var sut = new SkenderTechnicalIndicatorCalculator();
        var bars = BuildBars(14);

        var result = sut.ComputeRsi14(bars);

        Assert.Null(result);
    }

    [Fact]
    public void ComputeMovingAverages_ReturnsNulls_WhenNoBars()
    {
        var sut = new SkenderTechnicalIndicatorCalculator();

        var (ma50, ma200) = sut.ComputeMovingAverages([]);

        Assert.Null(ma50);
        Assert.Null(ma200);
    }

    [Fact]
    public void ComputeTwentyDayHighLow_ReturnsNulls_WhenLessThan20Bars()
    {
        var sut = new SkenderTechnicalIndicatorCalculator();
        var bars = BuildBars(19);

        var (high, low) = sut.ComputeTwentyDayHighLow(bars);

        Assert.Null(high);
        Assert.Null(low);
    }

    [Fact]
    public void Indicators_ReturnExpectedShapes_ForSufficientBars()
    {
        var sut = new SkenderTechnicalIndicatorCalculator();
        var bars = BuildBars(260);

        var actualRsi = sut.ComputeRsi14(bars);
        var actualMas = sut.ComputeMovingAverages(bars);
        var actualRange = sut.ComputeTwentyDayHighLow(bars);

        Assert.NotNull(actualRsi);
        Assert.InRange(actualRsi!.Value, 0m, 100m);
        Assert.NotNull(actualMas.Ma50);
        Assert.NotNull(actualMas.Ma200);
        Assert.NotNull(actualRange.TwentyDayHigh);
        Assert.NotNull(actualRange.TwentyDayLow);
        Assert.True(actualRange.TwentyDayHigh >= actualRange.TwentyDayLow);
    }

    [Fact]
    public void AddServices_RegistersSkenderTechnicalIndicatorCalculator()
    {
        var services = new ServiceCollection();

        services.AddServices();

        using var provider = services.BuildServiceProvider();
        var calculator = provider.GetRequiredService<ITechnicalIndicatorCalculator>();

        Assert.IsType<SkenderTechnicalIndicatorCalculator>(calculator);
    }

    [Fact]
    public async Task TechnicalIndicatorsService_UsesInjectedCalculator()
    {
        var asOf = new DateTime(2026, 2, 20);
        var bars = BuildBars(220, startDate: asOf.AddDays(-219));
        var marketData = new StubMarketDataService(bars);
        var calculator = new StubIndicatorCalculator();
        var sut = new TechnicalIndicatorsService(marketData, calculator);

        var result = await sut.GetIndicatorsAsync("AAPL", asOf);

        Assert.Equal(55.5m, result.Rsi14);
        Assert.Equal(101m, result.Ma50);
        Assert.Equal(99m, result.Ma200);
        Assert.Equal(110m, result.TwentyDayHigh);
        Assert.Equal(90m, result.TwentyDayLow);
    }

    [Fact]
    public void AddApplicationAndInfrastructure_ResolvesTechnicalIndicatorsServiceAndCalculator()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection([])
            .Build();

        var services = new ServiceCollection();
        services.AddInfrastructure(config);
        services.AddApplication(config);

        using var provider = services.BuildServiceProvider();
        var indicatorsService = provider.GetRequiredService<ITechnicalIndicatorsService>();
        var calculator = provider.GetRequiredService<ITechnicalIndicatorCalculator>();

        Assert.NotNull(indicatorsService);
        Assert.IsType<SkenderTechnicalIndicatorCalculator>(calculator);
    }

    private static List<OhlcvBar> BuildBars(int count, DateTime? startDate = null)
    {
        var start = startDate?.Date ?? new DateTime(2025, 1, 1);
        var bars = new List<OhlcvBar>(count);
        decimal price = 100m;

        for (int i = 0; i < count; i++)
        {
            var wave = (i % 10) - 5;
            price += wave * 0.25m;
            bars.Add(new OhlcvBar
            {
                Date = start.AddDays(i),
                Open = price - 0.3m,
                High = price + 1.2m,
                Low = price - 1.1m,
                Close = price,
                Volume = 1_000_000 + i
            });
        }

        return bars;
    }

    private sealed class StubIndicatorCalculator : ITechnicalIndicatorCalculator
    {
        public decimal? ComputeRsi14(IReadOnlyList<OhlcvBar> bars) => 55.5m;

        public (decimal? Ma50, decimal? Ma200) ComputeMovingAverages(IReadOnlyList<OhlcvBar> bars) => (101m, 99m);

        public (decimal? TwentyDayHigh, decimal? TwentyDayLow) ComputeTwentyDayHighLow(IReadOnlyList<OhlcvBar> bars) => (110m, 90m);
    }

    private sealed class StubMarketDataService(IReadOnlyList<OhlcvBar> bars) : IMarketDataService
    {
        public Task<StockQuote?> GetCurrentPriceAsync(string ticker, CancellationToken cancellationToken = default)
            => Task.FromResult<StockQuote?>(null);

        public Task<IReadOnlyList<OhlcvBar>> GetHistoricalPricesAsync(
            string ticker,
            DateTime from,
            DateTime to,
            string? interval = "1D",
            CancellationToken cancellationToken = default)
            => Task.FromResult(bars);

        public Task<OptionChainSnapshot?> GetOptionChainAsync(string ticker, CancellationToken cancellationToken = default)
            => Task.FromResult<OptionChainSnapshot?>(null);
    }
}
