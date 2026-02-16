namespace Backend.Domain.Models.MarketData
{
    /// <summary>
    /// Option sensitivity values used for strike selection.
    /// </summary>
    public class OptionGreeks
    {
        public decimal? Delta { get; set; }

        public decimal? Gamma { get; set; }

        public decimal? Theta { get; set; }

        public decimal? Vega { get; set; }
    }
}
