using Microsoft.EntityFrameworkCore;
using Backend.Infrastructure.Data.Entities;
using Backend.Domain.Models.Wheel;

namespace Backend.Infrastructure.Data
{
    public class AppDbContext : DbContext
    {
        public AppDbContext(DbContextOptions<AppDbContext> options) : base(options)
        {
        }

        public DbSet<WheelTickerStateEntity> WheelTickerStates => Set<WheelTickerStateEntity>();

        public DbSet<WheelEventEntity> WheelEvents => Set<WheelEventEntity>();

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            modelBuilder.Entity<WheelTickerStateEntity>(entity =>
            {
                entity.ToTable("wheel_ticker_states");
                entity.HasKey(x => x.Ticker);
                entity.Property(x => x.Ticker).HasMaxLength(16);
                entity.Property(x => x.ActiveOption).HasConversion<short>();
                entity.Property(x => x.CostBasis).HasPrecision(18, 6);
                entity.Property(x => x.Strike).HasPrecision(18, 6);
                entity.Property(x => x.OpenPremium).HasPrecision(18, 6);
                entity.Property(x => x.UpdatedAtUtc).IsRequired();
                entity.Property(x => x.Version).IsConcurrencyToken();
            });

            modelBuilder.Entity<WheelEventEntity>(entity =>
            {
                entity.ToTable("wheel_events");
                entity.HasKey(x => x.Id);
                entity.Property(x => x.Id).ValueGeneratedOnAdd();
                entity.Property(x => x.Ticker).HasMaxLength(16).IsRequired();
                entity.Property(x => x.EventType).HasConversion<short>();
                entity.Property(x => x.ActiveOptionBefore).HasConversion<short?>();
                entity.Property(x => x.ActiveOptionAfter).HasConversion<short?>();
                entity.Property(x => x.CloseReason).HasConversion<short?>();
                entity.Property(x => x.CostBasisBefore).HasPrecision(18, 6);
                entity.Property(x => x.CostBasisAfter).HasPrecision(18, 6);
                entity.Property(x => x.MetadataJson).HasColumnType("jsonb");
                entity.HasIndex(x => x.Ticker);
                entity.HasIndex(x => new { x.Ticker, x.OccurredAtUtc });
                entity.HasIndex(x => x.MetadataJson).HasMethod("gin");
            });
        }
    }
}
