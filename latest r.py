#!/usr/bin/env python3
"""
Multi-DEX RWA Assets Comparison Tool
Integrates with: Hyperliquid, Lighter, Ostium, Avantis
Compare opening/closing fees and spreads across multiple order sizes
"""

import requests
import time
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# ==================== CONFIGURATION ====================

# Order sizes in USD
ORDER_SIZES = [10_000, 100_000, 1_000_000, 10_000_000]  # $10K, $100K, $1M, $10M

# Fee Structures (Market Orders - Taker Fees)
FEE_STRUCTURES = {
    'hyperliquid': {
        'taker': 3.5,  # 3.5 bps
        'name': 'Hyperliquid'
    },
    'lighter': {
        'taker': 0.0,  # 0 bps during Season 2
        'name': 'Lighter'
    },
    'ostium': {
        # Opening fees (taker) - from Ostium docs
        'crypto': 10,      # 10 bps (maker: 3, taker: 10)
        'indices': 5,      # 5 bps
        'forex': 3,        # 3 bps
        'stocks': 5,       # 5 bps
        'gold': 3,         # 3 bps (XAU/USD)
        'silver': 15,      # 15 bps (XAG/USD)
        'oracle_fee': 0.10, # $0.10 per trade
        'closing': 0,      # No closing fee
        'name': 'Ostium'
    },
    'avantis': {
        # Fixed-Fee Perpetuals (Non-zero fee) - from official docs
        'forex_major': {'opening': 3, 'closing': 3},       # USDJPY, GBPUSD, EURUSD
        'forex_minor': {'opening': 5, 'closing': 5},       # Other forex
        'gold': {'opening': 6, 'closing': 0},              # XAU/USD - 6 bps opening, 0 closing
        'silver': {'opening': 6.35, 'closing': 0},         # XAG/USD
        'indices': {'opening': 6, 'closing': 0},           # SPY, QQQ
        'equities': {'opening': 6, 'closing': 0},          # Stocks - 6 bps opening, 0 closing
        'crypto_major': {'opening': 6, 'closing': 6},      # BTC, ETH, SOL
        'crypto_alt': {'opening': 8, 'closing': 8},        # Other crypto
        'name': 'Avantis (Fixed-Fee)'
    }
}

# Zero-slippage assets on Avantis
AVANTIS_ZERO_SLIPPAGE = {
    'XAUUSD', 'USDJPY', 'GBPUSD', 'EURUSD', 'QQQUSD', 'SPYUSD'
}

# Asset Mapping across DEXes
ASSET_MAPPING = {
    'AAPL': {
        'hyperliquid': 'AAPL',
        'lighter': 'AAPL',
        'ostium': 'AAPL',
        'avantis': 'AAPL',
        'category': 'equities'
    },
    'MSFT': {
        'hyperliquid': 'MSFT',
        'lighter': 'MSFT',
        'ostium': 'MSFT',
        'avantis': 'MSFT',
        'category': 'equities'
    },
    'GOOG': {
        'hyperliquid': 'GOOGL',  # Different: GOOGL on HL
        'lighter': 'GOOGL',      # GOOGL on Lighter
        'ostium': 'GOOG',        # GOOG on Ostium
        'avantis': 'GOOG',       # GOOG on Avantis
        'category': 'equities'
    },
    'AMZN': {
        'hyperliquid': 'AMZN',
        'lighter': 'AMZN',
        'ostium': 'AMZN',
        'avantis': 'AMZN',
        'category': 'equities'
    },
    'META': {
        'hyperliquid': 'META',
        'lighter': 'META',
        'ostium': 'META',
        'avantis': 'META',
        'category': 'equities'
    },
    'TSLA': {
        'hyperliquid': 'TSLA',
        'lighter': 'TSLA',
        'ostium': 'TSLA',
        'avantis': 'TSLA',
        'category': 'equities'
    },
    'NVDA': {
        'hyperliquid': 'NVDA',
        'lighter': 'NVDA',
        'ostium': 'NVDA',
        'avantis': 'NVDA',
        'category': 'equities'
    },
    'SPY': {
        'hyperliquid': 'SPY',
        'lighter': 'SPY',
        'ostium': 'SPY',
        'avantis': 'SPYUSD',     # SPYUSD on Avantis (zero slippage)
        'category': 'indices'
    },
    'QQQ': {
        'hyperliquid': 'QQQ',
        'lighter': 'QQQ',
        'ostium': 'QQQ',
        'avantis': 'QQQUSD',     # QQQUSD on Avantis (zero slippage)
        'category': 'indices'
    },
    'GOLD': {
        'hyperliquid': 'PAXG',   # PAXG on Hyperliquid
        'lighter': 'XAU',        # XAU on Lighter
        'ostium': 'XAUUSD',      # XAUUSD on Ostium
        'avantis': 'XAUUSD',     # XAUUSD on Avantis (zero slippage)
        'category': 'gold'
    },
    'USDJPY': {
        'hyperliquid': 'USDJPY',
        'lighter': 'USDJPY',
        'ostium': 'USDJPY',
        'avantis': 'USDJPY',     # Zero slippage on Avantis
        'category': 'forex_major'
    },
    'GBPUSD': {
        'hyperliquid': 'GBPUSD',
        'lighter': 'GBPUSD',
        'ostium': 'GBPUSD',
        'avantis': 'GBPUSD',     # Zero slippage on Avantis
        'category': 'forex_major'
    },
    'EURUSD': {
        'hyperliquid': 'EURUSD',
        'lighter': 'EURUSD',
        'ostium': 'EURUSD',
        'avantis': 'EURUSD',     # Zero slippage on Avantis
        'category': 'forex_major'
    }
}

# ==================== API CLIENTS ====================

class HyperliquidClient:
    """Client for Hyperliquid API"""
    
    BASE_URL = 'https://api.hyperliquid.xyz/info'
    
    @staticmethod
    def get_orderbook(coin: str) -> Optional[Dict]:
        """Fetch L2 orderbook"""
        try:
            response = requests.post(
                HyperliquidClient.BASE_URL,
                json={'type': 'l2Book', 'coin': coin},
                timeout=10000
            )
            response.raise_for_status()
            data = response.json()
            
            bids = data['levels'][0]
            asks = data['levels'][1]
            
            if not bids or not asks:
                return None
            
            best_bid = float(bids[0]['px'])
            best_ask = float(asks[0]['px'])
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_bps = (spread / mid_price) * 10000
            
            return {
                'mid_price': mid_price,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread_bps': spread_bps,
                'bids': bids,
                'asks': asks
            }
        except Exception as e:
            print(f"    ⚠️  Hyperliquid error: {str(e)}")
            return None


class LighterClient:
    """Client for Lighter API"""
    
    BASE_URL = 'https://mainnet.zklighter.elliot.ai/api/v1'
    
    @staticmethod
    def get_orderbook(symbol: str) -> Optional[Dict]:
        """Fetch orderbook from Lighter"""
        try:
            response = requests.get(
                f"{LighterClient.BASE_URL}/orderBookDetails",
                params={'symbol': symbol}
                # timeout=10000
            )
            
            if response.status_code != 200:
                print(f"    ⚠️  Lighter returned status {response.status_code}")
                return None
            
            data = response.json()
            
            if not data or 'bids' not in data or 'asks' not in data:
                print(f"    ⚠️  Lighter: No orderbook for {symbol}")
                return None
            
            bids = data['bids']
            asks = data['asks']
            
            if not bids or not asks:
                return None
            
            # Parse Lighter format
            best_bid = float(bids[0]['price']) if isinstance(bids[0], dict) else float(bids[0][0])
            best_ask = float(asks[0]['price']) if isinstance(asks[0], dict) else float(asks[0][0])
            
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_bps = (spread / mid_price) * 10000
            
            return {
                'mid_price': mid_price,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread_bps': spread_bps,
                'bids': bids,
                'asks': asks
            }
        except Exception as e:
            print(f"    ⚠️  Lighter error: {str(e)}")
            return None


class OstiumClient:
    """Client for Ostium - using Ostium Python SDK"""
    
    @staticmethod
    def get_data(symbol: str, category: str) -> Dict:
        """
        Get Ostium data
        Note: Ostium SDK would be used here: from ostium import OstiumSDK
        For now, returning fee structure based on category
        Spread = difference between executed price vs oracle price
        """
        try:
            # TODO: Integrate actual Ostium SDK when available
            # from ostium import OstiumSDK
            # sdk = OstiumSDK()
            # oracle_price = sdk.get_oracle_price(symbol)
            # executed_price = sdk.get_execution_price(symbol)
            # spread_bps = abs((executed_price - oracle_price) / oracle_price) * 10000
            
            # For now, using estimated spread
            estimated_spread_bps = 3.0  # Placeholder
            
            # Get opening fee based on category
            if category == 'equities':
                opening_fee = FEE_STRUCTURES['ostium']['stocks']
            elif category == 'indices':
                opening_fee = FEE_STRUCTURES['ostium']['indices']
            elif category in ['forex_major', 'forex_minor']:
                opening_fee = FEE_STRUCTURES['ostium']['forex']
            elif category == 'gold':
                opening_fee = FEE_STRUCTURES['ostium']['gold']
            elif category == 'silver':
                opening_fee = FEE_STRUCTURES['ostium']['silver']
            else:
                opening_fee = FEE_STRUCTURES['ostium']['crypto']
            
            return {
                'spread_bps': estimated_spread_bps,
                'opening_fee_bps': opening_fee,
                'closing_fee_bps': FEE_STRUCTURES['ostium']['closing'],
                'oracle_fee': FEE_STRUCTURES['ostium']['oracle_fee'],
                'note': 'Spread = executed vs oracle (estimated)'
            }
        except Exception as e:
            print(f"    ⚠️  Ostium error: {str(e)}")
            return None


class AvantisClient:
    """Client for Avantis - using Avantis SDK"""
    
    @staticmethod
    def get_data(symbol: str, category: str) -> Dict:
        """
        Get Avantis data
        Note: Avantis SDK would be used here
        For now, using fee structure from documentation
        """
        try:
            # TODO: Integrate actual Avantis SDK
            # from avantis_sdk import AvantisSDK
            # sdk = AvantisSDK()
            # market_data = sdk.get_market(symbol)
            
            # Get fee structure based on category
            if category == 'equities':
                fees = FEE_STRUCTURES['avantis']['equities']
            elif category == 'indices':
                fees = FEE_STRUCTURES['avantis']['indices']
            elif category == 'forex_major':
                fees = FEE_STRUCTURES['avantis']['forex_major']
            elif category == 'forex_minor':
                fees = FEE_STRUCTURES['avantis']['forex_minor']
            elif category == 'gold':
                fees = FEE_STRUCTURES['avantis']['gold']
            elif category == 'silver':
                fees = FEE_STRUCTURES['avantis']['silver']
            else:
                fees = FEE_STRUCTURES['avantis']['crypto_major']
            
            # Check if zero slippage asset
            is_zero_slippage = symbol in AVANTIS_ZERO_SLIPPAGE
            
            return {
                'spread_bps': 0.0 if is_zero_slippage else 2.0,
                'opening_fee_bps': fees['opening'],
                'closing_fee_bps': fees['closing'],
                'zero_slippage': is_zero_slippage,
                'note': 'Zero slippage' if is_zero_slippage else 'Fixed-fee perps'
            }
        except Exception as e:
            print(f"    ⚠️  Avantis error: {str(e)}")
            return None


# ==================== EXECUTION COST CALCULATION ====================

def calculate_execution_cost(orderbook: Dict, order_size_usd: float, fee_bps: float) -> Optional[Dict]:
    """Calculate execution cost for market buy order"""
    if not orderbook or 'asks' not in orderbook:
        return None
    
    asks = orderbook['asks']
    mid_price = orderbook['mid_price']
    
    remaining_usd = order_size_usd
    total_coins = 0
    total_cost = 0
    
    for level in asks:
        if remaining_usd <= 0:
            break
        
        # Parse level (different formats)
        if isinstance(level, dict):
            price = float(level.get('px') or level.get('price', 0))
            size = float(level.get('sz') or level.get('size', 0))
        else:
            price = float(level[0])
            size = float(level[1])
        
        if price <= 0 or size <= 0:
            continue
        
        # Calculate fill
        max_coins = remaining_usd / price
        filled = min(max_coins, size)
        cost = filled * price
        
        total_coins += filled
        total_cost += cost
        remaining_usd -= cost
    
    if remaining_usd > 1:  # More than $1 remaining = insufficient liquidity
        return None
    
    if total_coins == 0:
        return None
    
    avg_price = total_cost / total_coins
    slippage_bps = ((avg_price - mid_price) / mid_price) * 10000
    fee_dollars = total_cost * (fee_bps / 10000)
    total_bps = slippage_bps + fee_bps
    
    return {
        'avg_price': avg_price,
        'slippage_bps': slippage_bps,
        'fee_bps': fee_bps,
        'fee_dollars': fee_dollars,
        'total_cost_bps': total_bps
    }


# ==================== COMPARISON LOGIC ====================

def compare_asset(asset: str, order_sizes: List[int]) -> Dict:
    """Compare asset across all DEXes for multiple order sizes"""
    
    print(f"\n{'='*140}")
    print(f"📊 COMPARING: {asset} ({ASSET_MAPPING[asset]['category'].upper()})")
    print('='*140)
    
    mapping = ASSET_MAPPING[asset]
    category = mapping['category']
    
    # Fetch orderbook data
    print(f"\n🔄 Fetching orderbook data...")
    
    hl_book = HyperliquidClient.get_orderbook(mapping['hyperliquid'])
    if hl_book:
        print(f"  ✅ Hyperliquid ({mapping['hyperliquid']}): ${hl_book['mid_price']:.4f} mid, {hl_book['spread_bps']:.2f} bps spread")
    
    lt_book = LighterClient.get_orderbook(mapping['lighter'])
    if lt_book:
        print(f"  ✅ Lighter ({mapping['lighter']}): ${lt_book['mid_price']:.4f} mid, {lt_book['spread_bps']:.2f} bps spread")
    
    os_data = OstiumClient.get_data(mapping['ostium'], category)
    if os_data:
        print(f"  ✅ Ostium ({mapping['ostium']}): {os_data['spread_bps']:.2f} bps spread (estimated)")
    
    av_data = AvantisClient.get_data(mapping['avantis'], category)
    if av_data:
        print(f"  ✅ Avantis ({mapping['avantis']}): {av_data['note']}")
    
    # Compare across order sizes
    print(f"\n{'─'*140}")
    print(f"{'Order Size':<15} {'DEX':<25} {'Mid Price':<14} {'Spread':<10} {'Open Fee':<11} {'Close Fee':<11} {'Fee ($)':<12} {'Total (bps)':<12}")
    print('─'*140)
    
    all_results = {}
    
    for size in order_sizes:
        size_results = []
        
        # Hyperliquid
        if hl_book:
            exec_cost = calculate_execution_cost(hl_book, size, FEE_STRUCTURES['hyperliquid']['taker'])
            if exec_cost:
                total_fee = exec_cost['fee_dollars']
                print(f"${size:>13,}  {'Hyperliquid':<25} ${hl_book['mid_price']:<13.4f} {exec_cost['slippage_bps']:>8.2f}  {exec_cost['fee_bps']:>9.2f}  {exec_cost['fee_bps']:>9.2f}  ${total_fee:>10.2f}  {exec_cost['total_cost_bps']:>10.2f}")
                size_results.append({
                    'dex': 'Hyperliquid',
                    'total_cost_bps': exec_cost['total_cost_bps'],
                    'fee_dollars': total_fee,
                    'has_data': True
                })
            else:
                print(f"${size:>13,}  {'Hyperliquid':<25} ⚠️  Insufficient liquidity")
        
        # Lighter
        if lt_book:
            exec_cost = calculate_execution_cost(lt_book, size, FEE_STRUCTURES['lighter']['taker'])
            if exec_cost:
                total_fee = exec_cost['fee_dollars']
                print(f"{'':>15} {'Lighter':<25} ${lt_book['mid_price']:<13.4f} {exec_cost['slippage_bps']:>8.2f}  {exec_cost['fee_bps']:>9.2f}  {exec_cost['fee_bps']:>9.2f}  ${total_fee:>10.2f}  {exec_cost['total_cost_bps']:>10.2f}")
                size_results.append({
                    'dex': 'Lighter',
                    'total_cost_bps': exec_cost['total_cost_bps'],
                    'fee_dollars': total_fee,
                    'has_data': True
                })
            else:
                print(f"{'':>15} {'Lighter':<25} ⚠️  Insufficient liquidity")
        
        # Ostium
        if os_data:
            ref_price = (hl_book or lt_book)['mid_price'] if (hl_book or lt_book) else 100
            opening_fee = os_data['opening_fee_bps']
            closing_fee = os_data['closing_fee_bps']
            spread = os_data['spread_bps']
            total_bps = spread + opening_fee
            fee_dollars = size * (opening_fee / 10000) + os_data['oracle_fee']
            
            print(f"{'':>15} {'Ostium':<25} ${ref_price:<13.4f} {spread:>8.2f}  {opening_fee:>9.2f}  {closing_fee:>9.2f}  ${fee_dollars:>10.2f}  {total_bps:>10.2f}")
            size_results.append({
                'dex': 'Ostium',
                'total_cost_bps': total_bps,
                'fee_dollars': fee_dollars,
                'has_data': True
            })
        
        # Avantis
        if av_data:
            opening_fee = av_data['opening_fee_bps']
            closing_fee = av_data['closing_fee_bps']
            spread = av_data['spread_bps']
            total_bps = spread + opening_fee
            fee_dollars = size * (opening_fee / 10000)
            note = " ⭐" if av_data.get('zero_slippage') else ""
            
            print(f"{'':>15} {'Avantis (Fixed-Fee)':<25} ${'N/A':<13} {spread:>8.2f}  {opening_fee:>9.2f}  {closing_fee:>9.2f}  ${fee_dollars:>10.2f}  {total_bps:>10.2f}{note}")
            size_results.append({
                'dex': 'Avantis',
                'total_cost_bps': total_bps,
                'fee_dollars': fee_dollars,
                'has_data': True
            })
        
        print()
        all_results[size] = size_results
    
    return all_results


# ==================== INTERACTIVE MODE ====================

def interactive_mode():
    """Interactive CLI for asset and order size selection"""
    
    print("\n" + "="*140)
    print("💸 MULTI-DEX RWA COMPARISON TOOL")
    print("="*140)
    
    # Display available assets
    assets = list(ASSET_MAPPING.keys())
    print("\n📊 Available Assets:")
    for i, asset in enumerate(assets, 1):
        cat = ASSET_MAPPING[asset]['category']
        symbols = f"HL:{ASSET_MAPPING[asset]['hyperliquid']} | LT:{ASSET_MAPPING[asset]['lighter']} | OS:{ASSET_MAPPING[asset]['ostium']} | AV:{ASSET_MAPPING[asset]['avantis']}"
        print(f"  {i:2d}. {asset:<8} ({cat:<13}) [{symbols}]")
    
    # Asset selection
    print("\n🎯 Asset Selection:")
    print("  • Enter 'all' for all assets")
    print("  • Enter numbers: 1,2,3")
    print("  • Enter names: AAPL,TSLA,GOLD")
    
    choice = input("\nYour selection: ").strip()
    
    selected_assets = []
    if choice.lower() == 'all':
        selected_assets = assets
    elif choice.replace(',', '').replace(' ', '').isdigit():
        indices = [int(x.strip()) - 1 for x in choice.split(',') if x.strip()]
        selected_assets = [assets[i] for i in indices if 0 <= i < len(assets)]
    else:
        selected_assets = [a.strip().upper() for a in choice.split(',') if a.strip().upper() in assets]
    
    if not selected_assets:
        print("❌ No valid assets selected")
        return
    
    # Order size selection
    print(f"\n💰 Order Sizes:")
    print(f"  1. $10K")
    print(f"  2. $100K")
    print(f"  3. $1M")
    print(f"  4. $10M")
    print(f"  5. All sizes")
    print(f"  6. Custom (enter amounts)")
    
    size_choice = input("\nYour selection (default: all): ").strip() or "5"
    
    if size_choice == "1":
        order_sizes = [10_000]
    elif size_choice == "2":
        order_sizes = [100_000]
    elif size_choice == "3":
        order_sizes = [1_000_000]
    elif size_choice == "4":
        order_sizes = [10_000_000]
    elif size_choice == "5":
        order_sizes = ORDER_SIZES
    elif size_choice == "6":
        custom = input("Enter custom sizes (e.g., 50000,500000): ").strip()
        try:
            order_sizes = [int(x.strip()) for x in custom.split(',') if x.strip()]
        except:
            print("⚠️  Invalid format, using defaults")
            order_sizes = ORDER_SIZES
    else:
        order_sizes = ORDER_SIZES
    
    print(f"\n📊 Comparing {len(selected_assets)} asset(s) across {len(order_sizes)} order size(s)...")
    
    # Run comparisons
    all_results = {}
    for asset in selected_assets:
        results = compare_asset(asset, order_sizes)
        all_results[asset] = results
        time.sleep(0.5)  # Rate limiting
    
    # Summary report
    print("\n\n" + "="*140)
    print("📈 SUMMARY - CHEAPEST DEX BY ORDER SIZE")
    print("="*140)
    
    for size in order_sizes:
        print(f"\n💰 ${size:,} Orders:")
        print(f"{'Asset':<12} {'Cheapest DEX':<25} {'Total Cost (bps)':<20} {'Fee ($)':<15} {'Savings vs 2nd'}")
        print('─'*100)
        
        for asset, size_results in all_results.items():
            if size in size_results and size_results[size]:
                valid_results = [r for r in size_results[size] if r.get('has_data')]
                if valid_results:
                    sorted_results = sorted(valid_results, key=lambda x: x['total_cost_bps'])
                    cheapest = sorted_results[0]
                    savings = ""
                    if len(sorted_results) > 1:
                        diff = sorted_results[1]['total_cost_bps'] - cheapest['total_cost_bps']
                        savings = f"{diff:.2f} bps"
                    
                    print(f"{asset:<12} {cheapest['dex']:<25} {cheapest['total_cost_bps']:>18.2f}  ${cheapest['fee_dollars']:>13.2f}  {savings}")
    
    # Insights
    print("\n\n💡 KEY INSIGHTS:")
    print("  • ⭐ = Zero slippage on Avantis (XAU, USDJPY, GBPUSD, EURUSD, SPY, QQQ)")
    print("  • Lighter: 0% fees (best for small-medium orders)")
    print("  • Hyperliquid: 3.5 bps, consistent across all assets")
    print("  • Ostium: 3-15 bps + $0.10 oracle fee, 0 closing fee")
    print("  • Avantis: 3-8 bps opening, 0-8 bps closing, zero slippage on major pairs")
    print("  • Slippage increases with order size")
    
    # Save option
    save = input("\n💾 Save results to JSON? (y/n): ").strip().lower()
    if save == 'y':
        filename = f"dex_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"✅ Results saved to {filename}")


# ==================== MAIN ====================

def main():
    print("""
╔════════════════════════════════════════════════════════════════════════════════╗
║               MULTI-DEX RWA COMPARISON TOOL                                    ║
║               Compare Hyperliquid, Lighter, Ostium, Avantis                    ║
╚════════════════════════════════════════════════════════════════════════════════╝

📊 Features:
   • Real-time orderbook data (Hyperliquid, Lighter)
   • SDK integration ready (Ostium, Avantis)
   • Multiple order sizes ($10K - $10M)
   • Opening & closing fees
   • Spread analysis

🎯 Assets: AAPL, MSFT, GOOG, AMZN, META, TSLA, NVDA, SPY, QQQ, GOLD, Forex
    """)
    
    try:
        interactive_mode()
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()