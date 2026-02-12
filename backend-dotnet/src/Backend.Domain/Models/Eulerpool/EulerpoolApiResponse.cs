namespace Backend.Domain.Models.Eulerpool;

/// <summary>
/// Generic wrapper for Eulerpool API responses.
/// </summary>
/// <typeparam name="T">The type of data contained in the response</typeparam>
public class EulerpoolApiResponse<T>
{
    public T? Data { get; set; }
    public string? Status { get; set; }
    public string? Message { get; set; }
    public Dictionary<string, object>? Metadata { get; set; }
}

