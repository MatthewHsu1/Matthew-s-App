namespace FinancialApp.Domain.Options.Supabase
{
    public class SupabaseOptions
    {
        public const string SectionName = "Supabase";

        /// <summary>
        /// PostgreSQL connection string.
        /// </summary>
        public string ConnectionString { get; set; } = string.Empty;

    }
}
