using Backend.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Backend.Testing.Database;

public static class IntegrationTestDb
{
    private const string TestConnectionEnv = "BACKEND_TEST_DB_CONNECTION";

    public static async Task<IntegrationTestDbLease?> CreateAppDbContextLeaseAsync(string schemaPrefix = "it")
    {
        var baseConnection = ResolveBaseConnectionString();
        if (string.IsNullOrWhiteSpace(baseConnection))
            return null;

        var schema = $"{schemaPrefix}_test_{Guid.NewGuid():N}";

        var builder = new NpgsqlConnectionStringBuilder(baseConnection)
        {
            SearchPath = schema
        };

        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseNpgsql(builder.ConnectionString)
            .Options;

        try
        {
            await using var db = new AppDbContext(options);
            await db.Database.MigrateAsync();
        }
        catch (NpgsqlException)
        {
            return null;
        }

        return new IntegrationTestDbLease(options, schema);
    }

    private static string? ResolveBaseConnectionString()
    {
        var explicitOverride = Environment.GetEnvironmentVariable(TestConnectionEnv);
        if (!string.IsNullOrWhiteSpace(explicitOverride))
            return explicitOverride;

        try
        {
            var factory = new AppDbContextFactory();
            using var db = factory.CreateDbContext(Array.Empty<string>());
            return db.Database.GetConnectionString();
        }
        catch
        {
            return null;
        }
    }
}
