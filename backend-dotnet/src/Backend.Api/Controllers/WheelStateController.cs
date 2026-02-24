using Backend.Api.Contracts.Wheel;
using Backend.Application.Interfaces;
using Backend.Domain.Models.Wheel;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Backend.Api.Controllers;

[ApiController]
[Route("api/wheel-state")]
public sealed class WheelStateController(
    IWheelStateService wheelStateService,
    IWheelReconciliationService reconciliationService) : ControllerBase
{
    [HttpGet("{ticker}")]
    [ProducesResponseType(typeof(WheelStateResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> GetByTickerAsync(string ticker, CancellationToken cancellationToken)
    {
        Ticker normalizedTicker;
        try { normalizedTicker = new Ticker(ticker); }
        catch (ArgumentException ex) { return ValidationProblem(ex.Message); }

        var state = await wheelStateService.GetByTickerAsync(normalizedTicker, cancellationToken);

        if (state is null)
            return NotFound();

        return Ok(ToResponse(state));
    }

    [HttpPut("{ticker}")]
    [ProducesResponseType(typeof(WheelStateResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(WheelStateResponse), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> UpsertAsync(
        string ticker,
        [FromBody] UpsertWheelStateRequest request,
        CancellationToken cancellationToken)
    {
        var normalizedTicker = new Ticker(ticker);
        var existing = await wheelStateService.GetByTickerAsync(normalizedTicker, cancellationToken);

        var model = new WheelTickerState
        {
            Ticker = normalizedTicker,
            HasShares = request.HasShares,
            SharesOwned = request.SharesOwned,
            CostBasis = request.CostBasis,
            ActiveOption = request.ActiveOption,
            Strike = request.Strike,
            Expiration = request.Expiration,
            OpenPremium = request.OpenPremium,
            OpenedAtUtc = request.OpenedAtUtc,
            Version = request.Version ?? existing?.Version ?? 0
        };

        try
        {
            var updated = await wheelStateService.UpsertAsync(model, cancellationToken);
            var response = ToResponse(updated);

            if (existing is null)
                return CreatedAtAction(nameof(GetByTickerAsync), new { ticker = normalizedTicker.Value }, response);

            return Ok(response);
        }
        catch (ArgumentException ex)
        {
            return ValidationProblem(ex.Message);
        }
        catch (DbUpdateConcurrencyException ex)
        {
            return Conflict(new { message = ex.Message });
        }
    }

    [HttpPost("reconcile")]
    [ProducesResponseType(typeof(WheelReconcileResponse), StatusCodes.Status202Accepted)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> ReconcileAsync(
        [FromBody] ReconcileWheelStateRequest? request,
        CancellationToken cancellationToken)
    {
        IReadOnlyCollection<Ticker>? tickers = null;
        if (request?.Tickers is { Count: > 0 } rawTickers)
        {
            try
            {
                tickers = rawTickers.Select(t => new Ticker(t)).Distinct().ToArray();
            }
            catch (ArgumentException ex)
            {
                return ValidationProblem(ex.Message);
            }
        }

        var result = await reconciliationService.ReconcileAsync(tickers, cancellationToken);

        return Accepted(new WheelReconcileResponse
        {
            ProcessedTickers = result.ProcessedTickers,
            UpdatedTickers = result.UpdatedTickers,
            EventsAppended = result.EventsAppended
        });
    }

    private static WheelStateResponse ToResponse(WheelTickerState state)
    {
        return new WheelStateResponse
        {
            Ticker = state.Ticker.Value,
            HasShares = state.HasShares,
            SharesOwned = state.SharesOwned,
            CostBasis = state.CostBasis,
            ActiveOption = state.ActiveOption,
            Strike = state.Strike,
            Expiration = state.Expiration,
            OpenPremium = state.OpenPremium,
            OpenedAtUtc = state.OpenedAtUtc,
            UpdatedAtUtc = state.UpdatedAtUtc,
            Version = state.Version
        };
    }
}
