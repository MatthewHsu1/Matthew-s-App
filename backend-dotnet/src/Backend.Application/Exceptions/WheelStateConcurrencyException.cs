namespace Backend.Application.Exceptions;

public sealed class WheelStateConcurrencyException(string message) : Exception(message);
