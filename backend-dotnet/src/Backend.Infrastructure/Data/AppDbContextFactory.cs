using Backend.Domain.Options.Supabase;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;
using Microsoft.Extensions.Configuration;

namespace Backend.Infrastructure.Data
{
    /// <inheritdoc />
    public sealed class AppDbContextFactory : IDesignTimeDbContextFactory<AppDbContext>
    {
        /// <summary>
        /// User secrets ID of the Backend.Api project. Use the same secrets so design-time tools
        /// (e.g. EF migrations) read the same connection string as the API at runtime.
        /// </summary>
        private const string ApiUserSecretsId = "a9379190-9b8b-4ca8-b6f1-25f0f330cb20";

        /// <inheritdoc />
        public AppDbContext CreateDbContext(string[] args)
        {
            var configuration = new ConfigurationBuilder()
                .SetBasePath(Directory.GetCurrentDirectory())
                .AddJsonFile("appsettings.json", optional: true)
                .AddJsonFile("appsettings.Development.json", optional: true)
                .AddUserSecrets(ApiUserSecretsId)
                .Build();

            var connectionString = configuration
                .GetSection(SupabaseOptions.SectionName)[nameof(SupabaseOptions.MigrationConnection)]
                ?? throw new Exception("No connection string found for App DB Context.");

            var optionsBuilder = new DbContextOptionsBuilder<AppDbContext>();
            optionsBuilder.UseNpgsql(connectionString);

            return new AppDbContext(optionsBuilder.Options);
        }
    }
}
