using Backend.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;

namespace Backend.Testing.Database;

public sealed class IntegrationTestDbLease(
    DbContextOptions<AppDbContext> options,
    string schema) : IAsyncDisposable
{
    public DbContextOptions<AppDbContext> Options { get; } = options;

    public string Schema { get; } = schema;

    public async ValueTask DisposeAsync()
    {
        if (string.IsNullOrWhiteSpace(Schema))
            return;

        await using var db = new AppDbContext(Options);
#pragma warning disable EF1002
        await db.Database.ExecuteSqlRawAsync($"DROP SCHEMA IF EXISTS \"{Schema}\" CASCADE;");
#pragma warning restore EF1002
    }
}
