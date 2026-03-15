using System.Text.Json;

namespace Backend.Infrastructure.Extensions.Json
{
    /// <summary>
    /// Provides JSON parsing helpers for extracting string properties from known payload shapes.
    /// </summary>
    internal static class JsonDocumentExtensions
    {
        /// <summary>
        /// Reads a string property from a JSON object payload.
        /// </summary>
        /// <param name="json">JSON payload expected to be an object.</param>
        /// <param name="propertyName">Property name to read.</param>
        /// <param name="value">Resolved non-empty property value when found.</param>
        /// <returns><c>true</c> when a non-empty string property is found; otherwise <c>false</c>.</returns>
        internal static bool TryReadStringProperty(string json, string propertyName, out string? value)
        {
            value = null;
            try
            {
                using var doc = JsonDocument.Parse(json);
                if (doc.RootElement.ValueKind != JsonValueKind.Object)
                {
                    return false;
                }

                if (!doc.RootElement.TryGetProperty(propertyName, out var element) || element.ValueKind != JsonValueKind.String)
                {
                    return false;
                }

                value = element.GetString();
                return !string.IsNullOrWhiteSpace(value);
            }
            catch (JsonException)
            {
                return false;
            }
        }

        /// <summary>
        /// Reads a string property from the first object in a JSON array payload.
        /// </summary>
        /// <param name="json">JSON payload expected to be an array.</param>
        /// <param name="propertyName">Property name to read from the first object.</param>
        /// <param name="value">Resolved non-empty property value when found.</param>
        /// <returns><c>true</c> when a non-empty string property is found; otherwise <c>false</c>.</returns>
        internal static bool TryReadFirstArrayObjectProperty(string json, string propertyName, out string? value)
        {
            value = null;
            try
            {
                using var doc = JsonDocument.Parse(json);
                if (doc.RootElement.ValueKind != JsonValueKind.Array || doc.RootElement.GetArrayLength() == 0)
                {
                    return false;
                }

                var first = doc.RootElement[0];
                if (first.ValueKind != JsonValueKind.Object)
                {
                    return false;
                }

                if (!first.TryGetProperty(propertyName, out var element) || element.ValueKind != JsonValueKind.String)
                {
                    return false;
                }

                value = element.GetString();
                return !string.IsNullOrWhiteSpace(value);
            }
            catch (JsonException)
            {
                return false;
            }
        }
    }
}
