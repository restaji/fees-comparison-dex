#!/usr/bin/env python3
"""
Lighter Perp DEX Orderbook Analysis & Slippage Calculator
"""

import requests
import json
from typing import Optional, Dict, List

# Color codes for output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

class LighterDebugger:
    def __init__(self):
        self.base_url = "https://mainnet.zklighter.elliot.ai/api/v1"
        self.headers = {'Content-Type': 'application/json'}

    def get_orderbook(self, market_id: int, limit: int = 200) -> Optional[Dict]:
        """Fetch orderbook for a given market ID."""
        url = f"{self.base_url}/orderBookOrders?market_id={market_id}&limit={limit}"
        try:
            response = requests.get(url, headers=self.headers, timeout=1000)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"{RED}Error fetching orderbook: {e}{RESET}")
            return None

    def display_orderbook(self, orderbook: Dict, levels_to_show: int = 100):
        """Display orderbook in a readable format."""
        if not orderbook:
            print(f"{RED}No orderbook data available{RESET}")
            return

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            print(f"{RED}Empty orderbook{RESET}")
            return

        print(f"\n{CYAN}{'='*80}{RESET}")
        print(f"{CYAN}ORDERBOOK SNAPSHOT{RESET}")
        print(f"{CYAN}{'='*80}{RESET}\n")

        # Best bid/ask
        best_bid_price = float(bids[0]['price'])
        best_ask_price = float(asks[0]['price'])
        mid_price = (best_bid_price + best_ask_price) / 2
        spread = best_ask_price - best_bid_price
        spread_bps = (spread / mid_price) * 10000

        print(f"{GREEN}Best Bid:{RESET} ${best_bid_price:,.4f}")
        print(f"{RED}Best Ask:{RESET} ${best_ask_price:,.4f}")
        print(f"{YELLOW}Mid Price:{RESET} ${mid_price:,.4f}")
        print(f"{YELLOW}Spread:{RESET} ${spread:.4f} ({spread_bps:.2f} bps)\n")

        # Display asks (reversed to show best at bottom)
        print(f"{RED}{'ASKS (Sell Orders)':^80}{RESET}")
        print(f"{'Price':>15} | {'Size':>15} | {'Value (USD)':>20} | {'Cumulative USD':>20}")
        print("-" * 80)
        
        asks_to_show = min(levels_to_show, len(asks))
        cumulative_usd = 0
        for i in range(asks_to_show - 1, -1, -1):
            ask = asks[i]
            price = float(ask['price'])
            size = float(ask['remaining_base_amount'])
            value = price * size
            cumulative_usd += value
            print(f"${price:>14,.4f} | {size:>15,.4f} | ${value:>19,.2f} | ${cumulative_usd:>19,.2f}")

        print(f"\n{YELLOW}{'-'*80}{RESET}\n")

        # Display bids
        print(f"{GREEN}{'BIDS (Buy Orders)':^80}{RESET}")
        print(f"{'Price':>15} | {'Size':>15} | {'Value (USD)':>20} | {'Cumulative USD':>20}")
        print("-" * 80)
        
        bids_to_show = min(levels_to_show, len(bids))
        cumulative_usd = 0
        for i in range(bids_to_show):
            bid = bids[i]
            price = float(bid['price'])
            size = float(bid['remaining_base_amount'])
            value = price * size
            cumulative_usd += value
            print(f"${price:>14,.4f} | {size:>15,.4f} | ${value:>19,.2f} | ${cumulative_usd:>19,.2f}")

        print(f"{CYAN}{'='*80}{RESET}\n")

    def calculate_slippage(self, levels: List[Dict], order_size_usd: float, side: str = 'buy'):
        """
        Walk through orderbook and calculate execution details.
        
        Args:
            levels: List of price levels (asks for buy, bids for sell)
            order_size_usd: Order size in USD
            side: 'buy' or 'sell'
        """
        unfilled = order_size_usd
        total_qty = 0.0
        total_cost = 0.0
        filled_levels = 0

        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}WALKING ORDERBOOK - {side.upper()} ${order_size_usd:,.2f}{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")
        print(f"{'Level':>5} | {'Price':>12} | {'Available Size':>15} | {'Fill Size':>15} | {'Cost':>15} | {'Remaining':>15}")
        print("-" * 100)

        for level in levels:
            price = float(level['price'])
            qty = float(level['remaining_base_amount'])
            value = price * qty
            filled_levels += 1

            if unfilled <= value:
                # This level completes the order
                qty_needed = unfilled / price
                cost = unfilled
                total_qty += qty_needed
                total_cost += cost
                
                print(f"{filled_levels:>5} | ${price:>11,.4f} | {qty:>15,.4f} | {qty_needed:>15,.4f} | ${cost:>14,.2f} | ${0:>14,.2f}")
                unfilled = 0
                break
            else:
                # Take entire level
                total_qty += qty
                total_cost += value
                unfilled -= value
                
                print(f"{filled_levels:>5} | ${price:>11,.4f} | {qty:>15,.4f} | {qty:>15,.4f} | ${value:>14,.2f} | ${unfilled:>14,.2f}")

        print(f"{BLUE}{'='*80}{RESET}\n")

        avg_price = total_cost / total_qty if total_qty > 0 else 0
        filled = unfilled <= 0.0001

        return {
            'filled': filled,
            'remaining_usd': unfilled,
            'avg_price': avg_price,
            'levels_used': filled_levels,
            'total_qty': total_qty,
            'total_cost': total_cost
        }

    def analyze_execution(self, market_id: int, order_size_usd: float):
        """Fetch orderbook and analyze execution for both buy and sell."""
        print(f"\n{GREEN}{'='*80}{RESET}")
        print(f"{GREEN}LIGHTER PERP DEX - MARKET ID {market_id}{RESET}")
        print(f"{GREEN}Order Size: ${order_size_usd:,.2f}{RESET}")
        print(f"{GREEN}{'='*80}{RESET}")

        # Fetch orderbook
        orderbook = self.get_orderbook(market_id)
        if not orderbook:
            return

        # Display orderbook
        self.display_orderbook(orderbook)

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            print(f"{RED}Cannot calculate slippage - orderbook data incomplete{RESET}")
            return

        # Calculate mid price
        best_bid = float(bids[0]['price'])
        best_ask = float(asks[0]['price'])
        mid_price = (best_bid + best_ask) / 2

        # Analyze BUY execution (walk asks)
        buy_result = self.calculate_slippage(asks, order_size_usd, side='buy')

        # Analyze SELL execution (walk bids)
        sell_result = self.calculate_slippage(bids, order_size_usd, side='sell')

        # Display results
        print(f"\n{YELLOW}{'='*80}{RESET}")
        print(f"{YELLOW}EXECUTION SUMMARY{RESET}")
        print(f"{YELLOW}{'='*80}{RESET}\n")

        print(f"Mid Price: ${mid_price:,.4f}\n")

        # Buy side
        buy_slippage = 0.0
        if buy_result['filled']:
            buy_slippage = abs((buy_result['avg_price'] - mid_price) / mid_price) * 10000
            print(f"{GREEN}BUY ORDER:{RESET}")
            print(f"  Status: FULL FILL")
            print(f"  Avg Execution Price: ${buy_result['avg_price']:,.4f}")
            print(f"  Slippage (vs Mid): {buy_slippage:.2f} bps")
            print(f"  Levels Used: {buy_result['levels_used']}")
            print(f"  Total Quantity: {buy_result['total_qty']:,.4f}")
        else:
            filled_amt = order_size_usd - buy_result['remaining_usd']
            pct = (filled_amt / order_size_usd) * 100
            print(f"{RED}BUY ORDER:{RESET}")
            print(f"  Status: PARTIAL FILL")
            print(f"  Filled: ${filled_amt:,.2f} ({pct:.1f}%)")
            print(f"  Unfilled: ${buy_result['remaining_usd']:,.2f}")
            if filled_amt > 0:
                buy_slippage = abs((buy_result['avg_price'] - mid_price) / mid_price) * 10000
                print(f"  Avg Execution Price (Filled): ${buy_result['avg_price']:,.4f}")
                print(f"  Slippage (Filled Portion): {buy_slippage:.2f} bps")

        print()

        # Sell side
        sell_slippage = 0.0
        if sell_result['filled']:
            sell_slippage = abs((sell_result['avg_price'] - mid_price) / mid_price) * 10000
            print(f"{RED}SELL ORDER:{RESET}")
            print(f"  Status: FULL FILL")
            print(f"  Avg Execution Price: ${sell_result['avg_price']:,.4f}")
            print(f"  Slippage (vs Mid): {sell_slippage:.2f} bps")
            print(f"  Levels Used: {sell_result['levels_used']}")
            print(f"  Total Quantity: {sell_result['total_qty']:,.4f}")
        else:
            filled_amt = order_size_usd - sell_result['remaining_usd']
            pct = (filled_amt / order_size_usd) * 100
            print(f"{RED}SELL ORDER:{RESET}")
            print(f"  Status: PARTIAL FILL")
            print(f"  Filled: ${filled_amt:,.2f} ({pct:.1f}%)")
            print(f"  Unfilled: ${sell_result['remaining_usd']:,.2f}")
            if filled_amt > 0:
                sell_slippage = abs((sell_result['avg_price'] - mid_price) / mid_price) * 10000
                print(f"  Avg Execution Price (Filled): ${sell_result['avg_price']:,.4f}")
                print(f"  Slippage (Filled Portion): {sell_slippage:.2f} bps")

        # Average slippage
        if (buy_result['filled'] or buy_result['remaining_usd'] < order_size_usd) and \
           (sell_result['filled'] or sell_result['remaining_usd'] < order_size_usd):
            avg_slippage = (buy_slippage + sell_slippage) / 2
            print(f"\n{YELLOW}Average Slippage (Buy + Sell): {avg_slippage:.2f} bps{RESET}")

        print(f"\n{YELLOW}{'='*80}{RESET}\n")


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

    print(f"\n{GREEN}{'='*80}{RESET}")
    print(f"{GREEN}LIGHTER PERP DEX - ORDERBOOK & SLIPPAGE ANALYZER{RESET}")
    print(f"{GREEN}{'='*80}{RESET}\n")

    # Get user input
    try:
        raw_market = input("Enter Market ID (default: 128 for SPY): ").strip()
        market_id = int(raw_market) if raw_market else 128

        raw_size = input("Enter Order Size (e.g. 100k) [default: 100K]: ").strip().lower()
        if not raw_size:
            order_size = 100_000
        else:
            clean_sz = raw_size.replace(',', '').replace('_', '').replace('$', '')
            if 'k' in clean_sz:
                order_size = float(clean_sz.replace('k', '')) * 1000
            elif 'm' in clean_sz:
                order_size = float(clean_sz.replace('m', '')) * 1000000
            else:
                order_size = float(clean_sz)
    except:
        market_id = 128
        order_size = 100_000

    market_name = MARKETS.get(market_id, f"Market {market_id}")
    print(f"\n{YELLOW}Analyzing: {market_name}{RESET}")

    debugger.analyze_execution(market_id, order_size)

    print(f"{GREEN}Done.{RESET}\n")
