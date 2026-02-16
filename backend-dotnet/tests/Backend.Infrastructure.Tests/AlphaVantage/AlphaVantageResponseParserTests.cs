using Backend.Domain.Models.AlphaVantage;
using Backend.Domain.Models.MarketData;
using Backend.Infrastructure.Services.AlphaVantage;

namespace Backend.Infrastructure.Tests.AlphaVantage;

public class AlphaVantageResponseParserTests
{
    [Fact]
    public void ParseOptionChainSnapshot_ParsesMixedContractsAndSortsDeterministically()
    {
        var rows = new[]
        {
            new HistoricalOptionsContractDto
            {
                ContractId = "AAPL250117P00190000", Type = "put", Strike = "190", Expiration = "2025-01-17",
                Bid = "4.00", Ask = "4.40", Last = "4.25", ImpliedVolatility = "0.32",
                Delta = "-0.30", Gamma = "0.08", Theta = "-0.10", Vega = "0.20"
            },
            new HistoricalOptionsContractDto
            {
                ContractId = "AAPL241220C00180000", Type = "call", Strike = "180", Expiration = "2024-12-20",
                Bid = "6.00", Ask = "6.60", Last = "6.25", ImpliedVolatility = "0.28",
                Delta = "0.45", Gamma = "0.10", Theta = "-0.12", Vega = "0.18"
            },
            new HistoricalOptionsContractDto
            {
                ContractId = "AAPL241220P00180000", Type = "put", Strike = "180", Expiration = "2024-12-20",
                Bid = "2.00", Ask = "2.40", Last = "2.20", ImpliedVolatility = "0.26",
                Delta = "-0.22", Gamma = "0.07", Theta = "-0.08", Vega = "0.15"
            }
        };

        var result = AlphaVantageResponseParser.ParseOptionChainSnapshot("AAPL", 185m, DateTime.UtcNow, rows);

        Assert.Equal("AAPL", result.Ticker);
        Assert.Equal(185m, result.UnderlyingPrice);
        Assert.Equal(3, result.Contracts.Count);

        Assert.Collection(result.Contracts,
            first =>
            {
                Assert.Equal("AAPL241220C00180000", first.Symbol);
                Assert.Equal(OptionContractType.Call, first.Type);
                Assert.Equal(180m, first.Strike);
                Assert.Equal(new DateOnly(2024, 12, 20), first.Expiration);
                Assert.Equal(6.30m, first.Mid);
                Assert.Equal(6.30m, first.SelectedPremium);
                Assert.Equal(PremiumBasis.Mid, first.SelectedPremiumBasis);
                Assert.Equal(OptionMoneyness.ITM, first.Moneyness);
                Assert.NotNull(first.Greeks);
                Assert.True(first.HasCompleteGreeks);
                Assert.Null(first.SelectionEligibilityReason);
            },
            second =>
            {
                Assert.Equal("AAPL241220P00180000", second.Symbol);
                Assert.Equal(OptionContractType.Put, second.Type);
                Assert.Equal(180m, second.Strike);
                Assert.Equal(new DateOnly(2024, 12, 20), second.Expiration);
                Assert.Equal(2.20m, second.Mid);
                Assert.Equal(OptionMoneyness.OTM, second.Moneyness);
            },
            third =>
            {
                Assert.Equal("AAPL250117P00190000", third.Symbol);
                Assert.Equal(OptionContractType.Put, third.Type);
                Assert.Equal(190m, third.Strike);
                Assert.Equal(new DateOnly(2025, 1, 17), third.Expiration);
                Assert.Equal(4.20m, third.Mid);
                Assert.Equal(OptionMoneyness.ITM, third.Moneyness);
            });
    }

    [Fact]
    public void ParseOptionChainSnapshot_SkipsRowsWithInvalidTypeStrikeOrExpiration()
    {
        var rows = new[]
        {
            new HistoricalOptionsContractDto { ContractId = "AAPL_VALID", Type = "call", Strike = "200", Expiration = "2025-02-21" },
            new HistoricalOptionsContractDto { ContractId = "AAPL_BAD_TYPE", Type = "unknown", Strike = "200", Expiration = "2025-02-21" },
            new HistoricalOptionsContractDto { ContractId = "AAPL_BAD_STRIKE", Type = "put", Strike = "NaN", Expiration = "2025-02-21" },
            new HistoricalOptionsContractDto { ContractId = "AAPL_BAD_EXP", Type = "put", Strike = "200", Expiration = "21-02-2025" }
        };

        var result = AlphaVantageResponseParser.ParseOptionChainSnapshot("AAPL", 195m, DateTime.UtcNow, rows);

        var item = Assert.Single(result.Contracts);
        Assert.Equal("AAPL_VALID", item.Symbol);
    }

    [Fact]
    public void ParseOptionChainSnapshot_DeduplicatesByContractSymbol()
    {
        var rows = new[]
        {
            new HistoricalOptionsContractDto { ContractId = "AAPL_DUP", Type = "call", Strike = "210", Expiration = "2025-03-21" },
            new HistoricalOptionsContractDto { ContractId = "AAPL_DUP", Type = "call", Strike = "210", Expiration = "2025-03-21" }
        };

        var result = AlphaVantageResponseParser.ParseOptionChainSnapshot("AAPL", 205m, DateTime.UtcNow, rows);

        Assert.Single(result.Contracts);
    }

    [Fact]
    public void ParseOptionChainSnapshot_FallsBackSelectedPremiumAndFlagsMissingGreeks()
    {
        var rows = new[]
        {
            new HistoricalOptionsContractDto
            {
                ContractId = "AAPL_LAST_ONLY", Type = "put", Strike = "200", Expiration = "2025-03-21",
                Last = "3.10", Delta = null, Gamma = "0.02", Theta = "-0.01", Vega = "0.06"
            }
        };

        var result = AlphaVantageResponseParser.ParseOptionChainSnapshot("AAPL", 195m, DateTime.UtcNow, rows);

        var item = Assert.Single(result.Contracts);
        Assert.Null(item.Mid);
        Assert.Equal(3.10m, item.SelectedPremium);
        Assert.Equal(PremiumBasis.Last, item.SelectedPremiumBasis);
        Assert.False(item.HasCompleteGreeks);
        Assert.Equal("missing_greeks", item.SelectionEligibilityReason);
    }

    [Fact]
    public void ParseOptionChainSnapshot_ComputesAtmWithinTolerance()
    {
        var rows = new[]
        {
            new HistoricalOptionsContractDto
            {
                ContractId = "AAPL_ATM_CALL", Type = "call", Strike = "100.4", Expiration = "2025-03-21"
            },
            new HistoricalOptionsContractDto
            {
                ContractId = "AAPL_ATM_PUT", Type = "put", Strike = "99.6", Expiration = "2025-03-21"
            }
        };

        var result = AlphaVantageResponseParser.ParseOptionChainSnapshot("AAPL", 100m, DateTime.UtcNow, rows, PremiumBasis.Mid, 0.5m);

        Assert.All(result.Contracts, c => Assert.Equal(OptionMoneyness.ATM, c.Moneyness));
    }
}
