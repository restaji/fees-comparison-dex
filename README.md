# Fixed Fee Analysis

Compare total execution costs (slippage + fees) across perpetual DEXs.

## Overview

This tool compares slippage and trading fees across 7 decentralized perpetual exchanges:

- **Hyperliquid** - Orderbook-based DEX
- **Lighter** - Orderbook-based DEX  
- **Paradex** - Orderbook-based DEX
- **Aster** - Orderbook-based DEX
- **Avantis** - Oracle-based DEX
- **Ostium** - Oracle-based DEX
- **Extended** - Orderbook-based DEX (Starknet)

## Supported Assets

| Category | Assets |
|----------|--------|
| **Commodities** | Gold (XAU), Silver (XAG) |
| **Forex** | EUR/USD, GBP/USD, USD/JPY |
| **Stocks (MAG7)** | AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA |
| **Other** | COIN |

## Installation

```bash
# Install dependencies
pip install flask flask-cors requests

# Run the server
python slippage_api.py
```

## Usage

1. Open `http://127.0.0.1:5001` in your browser
2. Select an asset from the dropdown
3. Choose order size ($10K, $100K, $1M, $10M)
4. Results auto-refresh on selection

## Project Structure

```
├── slippage_api.py      # Backend API server
├── static/
│   └── styles.css       # Stylesheet
└── templates/
    └── index.html       # Frontend UI
```

## Features

- Real-time orderbook data fetching
- Slippage calculation based on order size
- Fee breakdown (opening, closing, spread)
- Auto-compare on asset/size selection
- Symbol display with exchange-specific tickers

## License

MIT
