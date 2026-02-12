namespace Backend.Application.Options
{
    /// <summary>
    /// Options for caching technical indicators (e.g. TTL when using IDistributedCache).
    /// </summary>
    public class TechnicalIndicatorsCacheOptions
    {
        public const string SectionName = "TechnicalIndicators";

        /// <summary>
        /// Cache TTL in minutes (e.g. 5–15). Default 10.
        /// </summary>
        public int CacheDurationMinutes { get; set; } = 10;
    }
}
