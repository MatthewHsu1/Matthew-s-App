using Backend.Domain.Models.AlphaVantage;
using Backend.Domain.Models.MarketData;
using Backend.Infrastructure.Services.AlphaVantage;

namespace Backend.Infrastructure.Tests.AlphaVantage;

public class AlphaVantageResponseParserTests
{
    [Fact]
    public void ParseOptionContracts_ParsesMixedContractsAndSortsDeterministically()
    {
        var rows = new[]
        {
            new HistoricalOptionsContractDto { ContractId = "AAPL250117P00190000", Type = "put", Strike = "190", Expiration = "2025-01-17" },
            new HistoricalOptionsContractDto { ContractId = "AAPL241220C00180000", Type = "call", Strike = "180", Expiration = "2024-12-20" },
            new HistoricalOptionsContractDto { ContractId = "AAPL241220P00180000", Type = "put", Strike = "180", Expiration = "2024-12-20" }
        };

        var result = AlphaVantageResponseParser.ParseOptionContracts(rows);

        Assert.Equal(3, result.Count);
        Assert.Collection(result,
            first =>
            {
                Assert.Equal("AAPL241220C00180000", first.Symbol);
                Assert.Equal(OptionContractType.Call, first.Type);
                Assert.Equal(180m, first.Strike);
                Assert.Equal(new DateOnly(2024, 12, 20), first.Expiration);
            },
            second =>
            {
                Assert.Equal("AAPL241220P00180000", second.Symbol);
                Assert.Equal(OptionContractType.Put, second.Type);
                Assert.Equal(180m, second.Strike);
                Assert.Equal(new DateOnly(2024, 12, 20), second.Expiration);
            },
            third =>
            {
                Assert.Equal("AAPL250117P00190000", third.Symbol);
                Assert.Equal(OptionContractType.Put, third.Type);
                Assert.Equal(190m, third.Strike);
                Assert.Equal(new DateOnly(2025, 1, 17), third.Expiration);
            });
    }

    [Fact]
    public void ParseOptionContracts_SkipsRowsWithInvalidTypeStrikeOrExpiration()
    {
        var rows = new[]
        {
            new HistoricalOptionsContractDto { ContractId = "AAPL_VALID", Type = "call", Strike = "200", Expiration = "2025-02-21" },
            new HistoricalOptionsContractDto { ContractId = "AAPL_BAD_TYPE", Type = "unknown", Strike = "200", Expiration = "2025-02-21" },
            new HistoricalOptionsContractDto { ContractId = "AAPL_BAD_STRIKE", Type = "put", Strike = "NaN", Expiration = "2025-02-21" },
            new HistoricalOptionsContractDto { ContractId = "AAPL_BAD_EXP", Type = "put", Strike = "200", Expiration = "21-02-2025" }
        };

        var result = AlphaVantageResponseParser.ParseOptionContracts(rows);

        var item = Assert.Single(result);
        Assert.Equal("AAPL_VALID", item.Symbol);
    }

    [Fact]
    public void ParseOptionContracts_DeduplicatesByContractSymbol()
    {
        var rows = new[]
        {
            new HistoricalOptionsContractDto { ContractId = "AAPL_DUP", Type = "call", Strike = "210", Expiration = "2025-03-21" },
            new HistoricalOptionsContractDto { ContractId = "AAPL_DUP", Type = "call", Strike = "210", Expiration = "2025-03-21" }
        };

        var result = AlphaVantageResponseParser.ParseOptionContracts(rows);

        Assert.Single(result);
    }
}
