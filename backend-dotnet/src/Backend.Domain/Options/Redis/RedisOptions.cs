namespace Backend.Domain.Options.Redis
{
    public class RedisOptions
    {
        public const string SectionName = "Redis";

        /// <summary>
        /// Redis connection string.
        /// When null or empty, distributed cache falls back to in-memory.
        /// </summary>
        public string? Configuration { get; set; }

        /// <summary>
        /// Optional key prefix for cache keys (e.g. "Backend_").
        /// </summary>
        public string? InstanceName { get; set; }
    }
}
