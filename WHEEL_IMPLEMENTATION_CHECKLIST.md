# Wheel Strategy — Implementation Checklist

A concrete, step-by-step checklist of what to build for an automated Wheel options trading system.

---

## Phase 1: Foundation & Configuration

### 1.1 Project structure
- [ ] Create solution/project layout (e.g. API, Services, Domain, Infrastructure)
- [ ] Set up configuration management (appsettings, environment variables)
- [ ] Add secrets management for API keys and broker credentials

### 1.2 Universe configuration (static config)
- [ ] Define stock universe: list of tickers (e.g. AAPL, MSFT, SPY)
- [ ] Implement minimum liquidity rules:
  - [ ] Options volume threshold (e.g. min 500 contracts/day)
  - [ ] Max bid-ask spread (e.g. < 5% of mid)
- [ ] Define minimum stock price (e.g. > $20)
- [ ] Define position sizing rules:
  - [ ] Max capital per stock
  - [ ] Max % of portfolio per ticker
  - [ ] Max open positions total

### 1.3 Risk parameters (config)
- [ ] Max capital per stock
- [ ] Earnings blackout: days before/after earnings to skip
- [ ] IV floor: skip puts when IV < X percentile
- [ ] Falling-knife filter: pause if stock drops > X% in Y days
- [ ] Global kill switch / pause flag

---

## Phase 2: Data Layer

### 2.1 Market data integration
- [ ] Choose provider (e.g. Polygon, Alpha Vantage, broker's API)
- [ ] Implement current price feed per ticker
- [ ] Implement historical price fetch for indicators
- [ ] Add rate limiting and error handling

### 2.2 Technical indicators
- [ ] RSI (e.g. 14-period)
- [ ] Moving averages (50-day, 200-day or similar)
- [ ] Recent high/low (e.g. 20-day high, 20-day low) as support/resistance proxy
- [ ] Decide on cache/refresh frequency (e.g. every 5–15 min)

### 2.3 Options data integration
- [ ] Options chain API (strikes, expirations)
- [ ] Greeks: delta, gamma, theta, vega
- [ ] Implied volatility per strike
- [ ] Bid/ask and last price for premium
- [ ] Map strikes to underlying price for delta selection

---

## Phase 3: State Management

### 3.1 Wheel state model
- [ ] Define data model per ticker:
  ```
  - ticker: string
  - has_shares: bool
  - shares_owned: int
  - cost_basis: decimal (if applicable)
  - active_option: none | put | call
  - strike: decimal?
  - expiration: date?
  - open_premium: decimal?
  - opened_at: datetime?
  ```
- [ ] Handle multiple lots / partial positions if needed

### 3.2 State persistence
- [ ] Choose storage (SQLite, PostgreSQL, etc.)
- [ ] Create schema for wheel state
- [ ] Implement create/read/update for state per ticker
- [ ] Add migration strategy for schema changes

### 3.3 State reconciliation
- [ ] Sync state with broker positions (daily or on startup)
- [ ] Detect assignments from broker
- [ ] Handle expired options (mark as closed, update state)

---

## Phase 4: Decision Engine

### 4.1 Put-mode logic (no shares)
- [ ] Entry conditions:
  - [ ] `has_shares == false`
  - [ ] `active_option == none`
  - [ ] RSI < 35 (configurable)
  - [ ] Price near support or 50 MA (define "near", e.g. within 2%)
  - [ ] Not in earnings blackout
  - [ ] IV above floor
  - [ ] Not in falling-knife zone
- [ ] Strike selection:
  - [ ] Filter expirations (e.g. 7–14 DTE)
  - [ ] Target delta (e.g. 0.25–0.35)
  - [ ] Strike below support or at defined level
  - [ ] Min premium (e.g. 0.5–1% of strike)
- [ ] Pick single best strike and return order params

### 4.2 Call-mode logic (own shares)
- [ ] Entry conditions:
  - [ ] `has_shares == true`
  - [ ] `active_option == none`
  - [ ] RSI > 65 (configurable)
  - [ ] Price near resistance or extended above MA
  - [ ] Not in earnings blackout
  - [ ] Strike above cost basis
- [ ] Strike selection:
  - [ ] 7–14 DTE
  - [ ] Delta 0.25–0.35
  - [ ] Strike > cost basis
  - [ ] Min premium
- [ ] Pick best strike and return order params

### 4.3 Risk filters (shared)
- [ ] Check available buying power before put
- [ ] Check share quantity before call
- [ ] Verify ticker is in universe and passes liquidity rules
- [ ] Enforce max open positions

---

## Phase 5: Broker Integration

### 5.1 Broker API setup
- [ ] Choose broker (IBKR, Tastytrade, Tradier, etc.)
- [ ] Implement auth (OAuth, API key, etc.)
- [ ] Handle session keepalive / reconnect

### 5.2 Order placement
- [ ] Place cash-secured put
- [ ] Place covered call
- [ ] Handle order confirmation and rejections
- [ ] Idempotency to avoid duplicate orders

### 5.3 Position & assignment tracking
- [ ] Fetch current positions
- [ ] Fetch open option orders
- [ ] Detect assignments (position change + option closed)
- [ ] Subscribe to or poll for assignment events if supported

---

## Phase 6: Orchestration

### 6.1 Scheduler / runner
- [ ] Define run frequency (e.g. every 15 min during market hours)
- [ ] Loop over universe
- [ ] For each ticker: load state → run decision engine → place order if signal
- [ ] Respect market hours (e.g. 9:30–16:00 ET)

### 6.2 Flow control
- [ ] Load state → fetch market data → fetch options data → run decision → execute
- [ ] Handle failures without stopping whole run
- [ ] Implement retries with backoff for transient errors

---

## Phase 7: Monitoring & Observability

### 7.1 Logging
- [ ] Log each run (timestamp, tickers scanned)
- [ ] Log decisions (why put/call was or wasn't taken)
- [ ] Log orders (filled, rejected, partial)
- [ ] Log state changes (assignment, expiration)

### 7.2 Metrics to track
- [ ] Premium collected per ticker and total
- [ ] Effective cost basis after assignments
- [ ] Annualized return per ticker
- [ ] Time in put vs call state
- [ ] Assignment frequency
- [ ] Win rate (premium kept vs assigned)

### 7.3 Alerts (optional)
- [ ] Alert on order rejection
- [ ] Alert on assignment
- [ ] Alert on repeated failures

---

## Phase 8: Safety & Testing

### 8.1 Paper trading
- [ ] Use broker's paper trading API or simulated mode
- [ ] Run full flow without real money
- [ ] Validate logic and order flow end-to-end

### 8.2 Validation & safeguards
- [ ] Dry-run mode (evaluate but don't place orders)
- [ ] Max orders per day
- [ ] Manual approval gate (optional) before first live trades
- [ ] Kill switch to halt all trading

### 8.3 Unit tests
- [ ] Test indicator calculations
- [ ] Test decision logic with mocked data
- [ ] Test state transitions

---

## Implementation Order (Suggested)

1. **Phase 1** — Config and universe
2. **Phase 2** — Market + options data (can start with one provider)
3. **Phase 3** — State model and persistence
4. **Phase 4** — Decision engine (core logic)
5. **Phase 5** — Broker integration (paper first)
6. **Phase 6** — Orchestration and scheduler
7. **Phase 7** — Logging and metrics
8. **Phase 8** — Safety, testing, and validation

---

## Dependencies to Resolve Early

| Decision | Options | Notes |
|----------|---------|-------|
| Broker | IBKR, Tastytrade, Tradier | Affects API and auth |
| Market data | Polygon, Alpha Vantage, broker | Some brokers include data |
| Storage | SQLite, PostgreSQL | Depends on scale and hosting |
| Hosting | Local, cloud (Azure/AWS) | Affects scheduler and uptime |
| Language | C# (.NET), Python | Match your existing stack (e.g. Financial App) |
