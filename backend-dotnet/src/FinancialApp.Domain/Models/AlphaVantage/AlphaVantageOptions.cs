namespace FinancialApp.Domain.Models.AlphaVantage
{
    /// <summary>
    /// Options for the AlphaVantage API.
    /// </summary>
    public class AlphaVantageOptions
    {
        /// <summary>
        /// The section name for the AlphaVantage API.
        /// </summary>
        public const string SectionName = "AlphaVantage";

        /// <summary>
        /// The base URL for the AlphaVantage API.
        /// </summary>
        public string BaseUrl { get; set; } = "https://www.alphavantage.co";

        /// <summary>
        /// The API key for the AlphaVantage API.
        /// </summary>
        public string ApiKey { get; set; } = string.Empty;
    }
}
