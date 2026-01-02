using FinancialApp.Domain.Models;
using Microsoft.EntityFrameworkCore;

namespace FinancialApp.Infrastructure.Data
{
    public class AppDbContext : DbContext
    {
        public AppDbContext(DbContextOptions<AppDbContext> options) : base(options)
        {
        }

        public DbSet<Test> Test { get; set; }
    }
}