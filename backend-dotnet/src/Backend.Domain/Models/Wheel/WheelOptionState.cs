namespace Backend.Domain.Models.Wheel
{
    /// <summary>
    /// Option portion of wheel state (active put/call details).
    /// </summary>
    public sealed class WheelOptionState
    {
        /// <summary>
        /// Type of active option (None, Put, or Call).
        /// </summary>
        public ActiveOptionType ActiveOption { get; set; } = ActiveOptionType.None;

        /// <summary>
        /// Strike of the active option when not None.
        /// </summary>
        public decimal? Strike { get; set; }

        /// <summary>
        /// Expiration date of the active option when not None.
        /// </summary>
        public DateOnly? Expiration { get; set; }

        /// <summary>
        /// Premium received when the option was opened.
        /// </summary>
        public decimal? OpenPremium { get; set; }

        /// <summary>
        /// UTC timestamp when the option was opened.
        /// </summary>
        public DateTimeOffset? OpenedAtUtc { get; set; }
    }
}
