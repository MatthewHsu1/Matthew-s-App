using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace Backend.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddWheelStateTables : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "wheel_events",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Ticker = table.Column<string>(type: "character varying(16)", maxLength: 16, nullable: false),
                    EventType = table.Column<short>(type: "smallint", nullable: false),
                    OccurredAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    ActiveOptionBefore = table.Column<short>(type: "smallint", nullable: true),
                    ActiveOptionAfter = table.Column<short>(type: "smallint", nullable: true),
                    SharesOwnedBefore = table.Column<int>(type: "integer", nullable: true),
                    SharesOwnedAfter = table.Column<int>(type: "integer", nullable: true),
                    CostBasisBefore = table.Column<decimal>(type: "numeric(18,6)", precision: 18, scale: 6, nullable: true),
                    CostBasisAfter = table.Column<decimal>(type: "numeric(18,6)", precision: 18, scale: 6, nullable: true),
                    CloseReason = table.Column<short>(type: "smallint", nullable: true),
                    MetadataJson = table.Column<string>(type: "jsonb", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_wheel_events", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "wheel_ticker_states",
                columns: table => new
                {
                    Ticker = table.Column<string>(type: "character varying(16)", maxLength: 16, nullable: false),
                    HasShares = table.Column<bool>(type: "boolean", nullable: false),
                    SharesOwned = table.Column<int>(type: "integer", nullable: false),
                    CostBasis = table.Column<decimal>(type: "numeric(18,6)", precision: 18, scale: 6, nullable: true),
                    ActiveOption = table.Column<short>(type: "smallint", nullable: false),
                    Strike = table.Column<decimal>(type: "numeric(18,6)", precision: 18, scale: 6, nullable: true),
                    Expiration = table.Column<DateOnly>(type: "date", nullable: true),
                    OpenPremium = table.Column<decimal>(type: "numeric(18,6)", precision: 18, scale: 6, nullable: true),
                    OpenedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    UpdatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    Version = table.Column<long>(type: "bigint", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_wheel_ticker_states", x => x.Ticker);
                });

            migrationBuilder.CreateIndex(
                name: "IX_wheel_events_Ticker",
                table: "wheel_events",
                column: "Ticker");

            migrationBuilder.CreateIndex(
                name: "IX_wheel_events_Ticker_OccurredAtUtc",
                table: "wheel_events",
                columns: new[] { "Ticker", "OccurredAtUtc" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "wheel_events");

            migrationBuilder.DropTable(
                name: "wheel_ticker_states");
        }
    }
}
