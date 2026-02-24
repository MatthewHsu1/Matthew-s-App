namespace Backend.Domain.Options.Supabase
{
    public class SupabaseOptions
    {
        public const string SectionName = "Supabase";

        /// <summary>
        /// PostgreSQL connection string.
        /// </summary>
        public string DefaultConnection { get; set; } = string.Empty;

        /// <summary>
        /// PostgreSQL connection string for migrations.
        /// </summary>
        public string MigrationConnection { get; set; } = string.Empty;

    }
}
