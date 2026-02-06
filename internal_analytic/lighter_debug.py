#!/usr/bin/env python3
"""
Lighter Perp DEX Orderbook Viewer
"""

import requests
from typing import Optional, Dict


class LighterDebugger:
    def __init__(self):
        self.base_url = "https://mainnet.zklighter.elliot.ai/api/v1"
        self.headers = {'Content-Type': 'application/json'}

    def get_orderbook(self, market_id: int, limit: int = 250) -> Optional[Dict]:
        """Fetch orderbook for a given market ID."""
        url = f"{self.base_url}/orderBookOrders?market_id={market_id}&limit={limit}"
        try:
            response = requests.get(url, headers=self.headers, timeout=1000)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching orderbook: {e}")
            return None

    def display_orderbook(self, orderbook: Dict, levels_to_show: int = 50):
        """Display orderbook in a simple table format."""
        if not orderbook:
            print("No orderbook data available")
            return

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids and not asks:
            print("Empty orderbook")
            return

        # Calculate mid price
        best_bid = float(bids[0]['price']) if bids else 0
        best_ask = float(asks[0]['price']) if asks else 0
        mid_price = (best_bid + best_ask) / 2

        print(f"\nBest Bid: ${best_bid:,.4f}")
        print(f"Best Ask: ${best_ask:,.4f}")
        print(f"Mid Price: ${mid_price:,.4f}")

        # Display asks (reversed to show best at bottom)
        print("\nASKS")
        print(f"{'Price':>15} | {'Size':>15} | {'Value (USD)':>20}")
        print("-" * 55)
        
        asks_to_show = min(levels_to_show, len(asks))
        for i in range(asks_to_show - 1, -1, -1):
            ask = asks[i]
            price = float(ask['price'])
            size = float(ask['remaining_base_amount'])
            value = price * size
            print(f"${price:>14,.4f} | {size:>15,.4f} | ${value:>19,.2f}")

        print("-" * 55)

        # Display bids
        print("\nBIDS")
        print(f"{'Price':>15} | {'Size':>15} | {'Value (USD)':>20}")
        print("-" * 55)
        
        bids_to_show = min(levels_to_show, len(bids))
        for i in range(bids_to_show):
            bid = bids[i]
            price = float(bid['price'])
            size = float(bid['remaining_base_amount'])
            value = price * size
            print(f"${price:>14,.4f} | {size:>15,.4f} | ${value:>19,.2f}")

        print("-" * 55)

    def calculate_slippage(self, levels: list, order_size_usd: float) -> Dict:
        """Walk through orderbook levels and calculate average execution price."""
        unfilled = order_size_usd
        total_qty = 0.0
        total_cost = 0.0

        for level in levels:
            price = float(level['price'])
            qty = float(level['remaining_base_amount'])
            value = price * qty

            if unfilled <= value:
                # This level completes the order
                qty_needed = unfilled / price
                total_qty += qty_needed
                total_cost += unfilled
                unfilled = 0
                break
            else:
                # Take entire level
                total_qty += qty
                total_cost += value
                unfilled -= value

        avg_price = total_cost / total_qty if total_qty > 0 else 0
        filled = unfilled <= 0.0001

        return {
            'filled': filled,
            'avg_price': avg_price,
            'total_qty': total_qty,
            'total_cost': total_cost,
            'remaining_usd': unfilled
        }

    def analyze_slippage(self, orderbook: Dict, order_size_usd: float = 100_000):
        """Calculate slippage for buy and sell sides."""
        if not orderbook:
            print("No orderbook data")
            return

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            print("Incomplete orderbook")
            return

        best_bid = float(bids[0]['price'])
        best_ask = float(asks[0]['price'])
        mid_price = (best_bid + best_ask) / 2

        print(f"\n{'='*55}")
        print(f"SLIPPAGE ANALYSIS (Order Size: ${order_size_usd:,.0f})")
        print(f"{'='*55}")

        # Buy side (walk asks)
        buy_result = self.calculate_slippage(asks, order_size_usd)
        if buy_result['filled']:
            buy_slippage_bps = abs((buy_result['avg_price'] - mid_price) / mid_price) * 10000
            print(f"\nBUY:")
            print(f"  Avg Exec Price: ${buy_result['avg_price']:,.4f}")
            print(f"  Slippage (vs Mid): {buy_slippage_bps:.2f} bps")
        else:
            filled_pct = (order_size_usd - buy_result['remaining_usd']) / order_size_usd * 100
            print(f"\nBUY: PARTIAL FILL ({filled_pct:.1f}%)")
            if buy_result['avg_price'] > 0:
                buy_slippage_bps = abs((buy_result['avg_price'] - mid_price) / mid_price) * 10000
                print(f"  Avg Exec Price: ${buy_result['avg_price']:,.4f}")
                print(f"  Slippage (vs Mid): {buy_slippage_bps:.2f} bps")

        # Sell side (walk bids)
        sell_result = self.calculate_slippage(bids, order_size_usd)
        if sell_result['filled']:
            sell_slippage_bps = abs((sell_result['avg_price'] - mid_price) / mid_price) * 10000
            print(f"\nSELL:")
            print(f"  Avg Exec Price: ${sell_result['avg_price']:,.4f}")
            print(f"  Slippage (vs Mid): {sell_slippage_bps:.2f} bps")
        else:
            filled_pct = (order_size_usd - sell_result['remaining_usd']) / order_size_usd * 100
            print(f"\nSELL: PARTIAL FILL ({filled_pct:.1f}%)")
            if sell_result['avg_price'] > 0:
                sell_slippage_bps = abs((sell_result['avg_price'] - mid_price) / mid_price) * 10000
                print(f"  Avg Exec Price: ${sell_result['avg_price']:,.4f}")
                print(f"  Slippage (vs Mid): {sell_slippage_bps:.2f} bps")

        print(f"{'='*55}")


# Market ID reference
MARKETS = {
    92: 'XAU/USD',
    93: 'XAG/USD',
    96: 'EUR/USD',
    97: 'GBP/USD',
    98: 'USD/JPY',
    109: 'COIN/USD',
    110: 'NVDA/USD',
    112: 'TSLA/USD',
    113: 'AAPL/USD',
    114: 'AMZN/USD',
    115: 'MSFT/USD',
    116: 'GOOG/USD',
    117: 'META/USD',
    128: 'SPY/USD',
    129: 'QQQ/USD',
}


if __name__ == "__main__":
    debugger = LighterDebugger()

    print("\nAvailable Markets:")
    for mid, name in MARKETS.items():
        print(f"  {mid}: {name}")

    try:
        raw_market = input("\nEnter Market ID (default: 128 for SPY): ").strip()
        market_id = int(raw_market) if raw_market else 128
    except:
        market_id = 128

    market_name = MARKETS.get(market_id, f"Market {market_id}")
    print(f"\nFetching orderbook for: {market_name}")

    orderbook = debugger.get_orderbook(market_id)
    debugger.display_orderbook(orderbook)
    debugger.analyze_slippage(orderbook, order_size_usd=100_000)
