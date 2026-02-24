using Backend.Domain.Models.Wheel;

namespace Backend.Infrastructure.Tests.Wheel;

public class TickerTests
{
    [Theory]
    [InlineData("aapl", "AAPL")]
    [InlineData("  msft  ", "MSFT")]
    [InlineData("TSLA", "TSLA")]
    [InlineData(" nvda", "NVDA")]
    public void Constructor_NormalizesValue(string input, string expected)
    {
        var ticker = new Ticker(input);
        Assert.Equal(expected, ticker.Value);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void Constructor_Throws_WhenValueIsEmptyOrWhitespace(string input)
    {
        Assert.Throws<ArgumentException>(() => new Ticker(input));
    }

    [Fact]
    public void ImplicitStringConversion_ReturnsValue()
    {
        var ticker = new Ticker("aapl");
        string s = ticker;
        Assert.Equal("AAPL", s);
    }

    [Fact]
    public void ToString_ReturnsValue()
    {
        var ticker = new Ticker("msft");
        Assert.Equal("MSFT", ticker.ToString());
    }

    [Fact]
    public void StructuralEquality_TwoTickersWithSameSymbol_AreEqual()
    {
        var a = new Ticker("aapl");
        var b = new Ticker("AAPL");
        Assert.Equal(a, b);
    }
}
