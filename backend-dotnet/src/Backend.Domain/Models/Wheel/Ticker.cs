namespace Backend.Domain.Models.Wheel
{
    /// <summary>
    /// A normalized ticker symbol (e.g. stock underlying). Always uppercase and trimmed.
    /// </summary>
    public readonly record struct Ticker
    {
        /// <summary>
        /// The normalized ticker string value.
        /// </summary>
        public string Value { get; }

        /// <summary>
        /// Initializes a <see cref="Ticker"/> by trimming and uppercasing <paramref name="value"/>.
        /// </summary>
        /// <param name="value">Raw ticker symbol. Must not be empty or whitespace.</param>
        /// <exception cref="ArgumentException">Thrown when <paramref name="value"/> is empty or whitespace.</exception>
        public Ticker(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                throw new ArgumentException("Ticker cannot be empty or whitespace.", nameof(value));
            Value = value.Trim().ToUpperInvariant();
        }

        /// <summary>
        /// Implicitly converts a <see cref="Ticker"/> to its string value.
        /// </summary>
        public static implicit operator string(Ticker t) => t.Value;

        /// <inheritdoc />
        public override string ToString() => Value;
    }
}
