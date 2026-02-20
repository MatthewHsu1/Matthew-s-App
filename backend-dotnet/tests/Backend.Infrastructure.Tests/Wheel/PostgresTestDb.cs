using Backend.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Backend.Infrastructure.Tests.Wheel;

internal static class PostgresTestDb
{
    private const string ConnectionEnv = "WHEEL_TEST_POSTGRES_CONNECTION";

    public static async Task<(DbContextOptions<AppDbContext>? options, string schema)> CreateOptionsAsync()
    {
        var baseConnection = Environment.GetEnvironmentVariable(ConnectionEnv);

        if (string.IsNullOrWhiteSpace(baseConnection))
            return (null, string.Empty);

        var schema = $"wheel_test_{Guid.NewGuid():N}";

        var builder = new NpgsqlConnectionStringBuilder(baseConnection)
        {
            SearchPath = schema
        };

        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseNpgsql(builder.ConnectionString)
            .Options;

        await using var db = new AppDbContext(options);
        await db.Database.MigrateAsync();

        return (options, schema);
    }

    public static async Task CleanupSchemaAsync(DbContextOptions<AppDbContext>? options, string schema)
    {
        if (options is null || string.IsNullOrWhiteSpace(schema))
            return;

        await using var db = new AppDbContext(options);
#pragma warning disable EF1002
        await db.Database.ExecuteSqlRawAsync($"DROP SCHEMA IF EXISTS \"{schema}\" CASCADE;");
#pragma warning restore EF1002
    }
}
