#!/usr/bin/env python3
"""
Multi-DEX RWA Assets Comparison Tool
Focus: Gold, Silver, Mag7, HOOD, SPY, QQQ, Major Forex
Exchanges: Hyperliquid, Lighter, Ostium, Avantis
"""

import requests
import time
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

# Try to import Ostium SDK (optional)
try:
    from ostium_python_sdk import OstiumSDK, NetworkConfig
    OSTIUM_SDK_AVAILABLE = True
except ImportError:
    OSTIUM_SDK_AVAILABLE = False
    print("⚠️  Ostium SDK not installed. Using REST API fallback.")
    print("   Install with: pip install ostium-python-sdk")

# ==================== CONFIGURATION ====================

ORDER_SIZES = [10_000, 100_000, 1_000_000, 10_000_000]

# Mag7 stocks
MAG7 = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA']

# Asset configurations
ALL_ASSETS = {
    # Commodities
    'GOLD': {'hl': 'PAXG', 'lt': 'XAU', 'os': 'XAUUSD', 'av': 'XAUUSD', 'cat': 'gold'},
    'SILVER': {'hl': 'XAGUSD', 'lt': 'XAG', 'os': 'XAGUSD', 'av': 'XAGUSD', 'cat': 'silver'},
    
    # Mag7
    'AAPL': {'hl': 'AAPL', 'lt': 'AAPL', 'os': 'AAPL', 'av': 'AAPL', 'cat': 'equities'},
    'MSFT': {'hl': 'MSFT', 'lt': 'MSFT', 'os': 'MSFT', 'av': 'MSFT', 'cat': 'equities'},
    'GOOGL': {'hl': 'GOOGL', 'lt': 'GOOGL', 'os': 'GOOG', 'av': 'GOOG', 'cat': 'equities'},
    'AMZN': {'hl': 'AMZN', 'lt': 'AMZN', 'os': 'AMZN', 'av': 'AMZN', 'cat': 'equities'},
    'META': {'hl': 'META', 'lt': 'META', 'os': 'META', 'av': 'META', 'cat': 'equities'},
    'TSLA': {'hl': 'TSLA', 'lt': 'TSLA', 'os': 'TSLA', 'av': 'TSLA', 'cat': 'equities'},
    'NVDA': {'hl': 'NVDA', 'lt': 'NVDA', 'os': 'NVDA', 'av': 'NVDA', 'cat': 'equities'},
    
    # Robinhood - Only HOOD
    'HOOD': {'hl': 'HOOD', 'lt': 'HOOD', 'os': 'HOOD', 'av': 'HOOD', 'cat': 'equities'},
    
    # Indices
    'SPY': {'hl': 'SPY', 'lt': 'SPY', 'os': 'SPY', 'av': 'SPYUSD', 'cat': 'indices'},
    'QQQ': {'hl': 'QQQ', 'lt': 'QQQ', 'os': 'QQQ', 'av': 'QQQUSD', 'cat': 'indices'},
    
    # Forex
    'EURUSD': {'hl': 'EURUSD', 'lt': 'EURUSD', 'os': 'EURUSD', 'av': 'EURUSD', 'cat': 'forex_major'},
    'USDJPY': {'hl': 'USDJPY', 'lt': 'USDJPY', 'os': 'USDJPY', 'av': 'USDJPY', 'cat': 'forex_major'},
    'GBPUSD': {'hl': 'GBPUSD', 'lt': 'GBPUSD', 'os': 'GBPUSD', 'av': 'GBPUSD', 'cat': 'forex_major'},
}

# Fee structures
FEES = {
    'hyperliquid': {
        'taker': 4.5,  # 4.5 bps (CORRECTED from 3.5)
        'name': 'Hyperliquid'
    },
    'lighter': {
        'taker': 0.0,  # 0 bps
        'name': 'Lighter'
    },
    'ostium': {
        'stocks': 5, 'indices': 5, 'forex': 3, 'gold': 3, 'silver': 15,
        'oracle_fee': 0.10,
        'name': 'Ostium'
    },
    'avantis': {
        'equities': {'opening': 6, 'closing': 0},
        'indices': {'opening': 6, 'closing': 0},
        'forex_major': {'opening': 3, 'closing': 3},
        'gold': {'opening': 6, 'closing': 0},
        'silver': {'opening': 6.35, 'closing': 0},
        'name': 'Avantis'
    }
}

AVANTIS_ZERO_SLIPPAGE = {'XAUUSD', 'USDJPY', 'GBPUSD', 'EURUSD', 'QQQUSD', 'SPYUSD'}

# ==================== API CLIENTS ====================

class HyperliquidClient:
    @staticmethod
    def get_orderbook(symbol: str) -> Optional[Dict]:
        try:
            response = requests.post(
                'https://api.hyperliquid.xyz/info',
                json={'type': 'l2Book', 'coin': symbol},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get('levels') or len(data['levels']) < 2:
                return None
            
            bids = [{'price': float(l['px']), 'qty': float(l['sz'])} for l in data['levels'][0]]
            asks = [{'price': float(l['px']), 'qty': float(l['sz'])} for l in data['levels'][1]]
            
            if not bids or not asks:
                return None
            
            best_bid = bids[0]['price']
            best_ask = asks[0]['price']
            mid = (best_bid + best_ask) / 2
            spread_bps = ((best_ask - best_bid) / mid) * 10000
            
            return {
                'mid_price': mid,
                'spread_bps': spread_bps,
                'bids': bids,
                'asks': asks
            }
        except Exception as e:
            print(f"    ⚠️  HL error: {str(e)}")
            return None


class LighterClient:
    @staticmethod
    def get_orderbook(symbol: str) -> Optional[Dict]:
        try:
            # Get market details
            details_res = requests.get(
                'https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails',
                timeout=10
            )
            details_res.raise_for_status()
            
            markets = details_res.json().get('order_book_details', [])
            market = next((m for m in markets if 
                          m.get('symbol', '').upper() == symbol.upper() and 
                          m.get('status') == 'active'), None)
            
            if not market:
                return None
            
            market_id = market['market_id']
            
            # Fetch orderbook
            ob_res = requests.get(
                f'https://mainnet.zklighter.elliot.ai/api/v1/orderBookOrders',
                params={'market_id': market_id, 'limit': 50},
                timeout=10
            )
            ob_res.raise_for_status()
            ob_data = ob_res.json()
            
            bids = [{'price': float(l['price']), 'qty': float(l['remaining_base_amount'])} 
                   for l in ob_data.get('bids', [])]
            asks = [{'price': float(l['price']), 'qty': float(l['remaining_base_amount'])} 
                   for l in ob_data.get('asks', [])]
            
            bids.sort(key=lambda x: x['price'], reverse=True)
            asks.sort(key=lambda x: x['price'])
            
            if not bids or not asks:
                return None
            
            best_bid = bids[0]['price']
            best_ask = asks[0]['price']
            mid = (best_bid + best_ask) / 2
            spread_bps = ((best_ask - best_bid) / mid) * 10000
            
            return {
                'mid_price': mid,
                'spread_bps': spread_bps,
                'bids': bids,
                'asks': asks
            }
        except Exception as e:
            print(f"    ⚠️  Lighter error: {str(e)}")
            return None


class OstiumClient:
    """Client for Ostium - with SDK integration or REST API fallback"""
    
    sdk = None
    
    @classmethod
    def initialize_sdk(cls):
        """Initialize Ostium SDK if available and configured"""
        if not OSTIUM_SDK_AVAILABLE:
            return False
        
        try:
            private_key = os.getenv('OSTIUM_PRIVATE_KEY')
            rpc_url = os.getenv('OSTIUM_RPC_URL')
            
            if not private_key or not rpc_url:
                print("    ℹ️  Ostium SDK: Set OSTIUM_PRIVATE_KEY and OSTIUM_RPC_URL env vars")
                return False
            
            config = NetworkConfig.mainnet()
            cls.sdk = OstiumSDK(config, private_key, rpc_url, verbose=False)
            return True
        except Exception as e:
            print(f"    ⚠️  Ostium SDK init error: {str(e)}")
            return False
    
    @classmethod
    def get_oracle_price(cls, symbol: str) -> Optional[float]:
        """Get oracle price from Ostium REST API"""
        try:
            response = requests.get(
                'https://metadata-backend.ostium.io/PricePublish/latest-prices',
                timeout=10
            )
            response.raise_for_status()
            prices = response.json()
            
            # Find matching symbol
            for price_data in prices:
                if price_data.get('pair', '').upper() == symbol.upper():
                    return float(price_data.get('price', 0))
            
            return None
        except Exception as e:
            return None
    
    @classmethod
    def get_data(cls, symbol: str, category: str) -> Dict:
        """Get Ostium fee data and estimated spread"""
        try:
            # Get fee based on category
            if category == 'equities':
                opening_fee = FEES['ostium']['stocks']
            elif category == 'indices':
                opening_fee = FEES['ostium']['indices']
            elif category in ['forex_major', 'forex_minor']:
                opening_fee = FEES['ostium']['forex']
            elif category == 'gold':
                opening_fee = FEES['ostium']['gold']
            elif category == 'silver':
                opening_fee = FEES['ostium']['silver']
            else:
                opening_fee = 5
            
            # Get oracle price if available
            oracle_price = cls.get_oracle_price(symbol)
            
            # Estimated spread (executed vs oracle)
            # In real implementation, would fetch actual execution price
            estimated_spread_bps = 3.0
            
            return {
                'oracle_price': oracle_price,
                'spread_bps': estimated_spread_bps,
                'opening_fee_bps': opening_fee,
                'closing_fee_bps': 0,
                'oracle_fee': FEES['ostium']['oracle_fee'],
                'note': 'Spread = executed vs oracle (estimated)'
            }
        except Exception as e:
            print(f"    ⚠️  Ostium error: {str(e)}")
            return None


# ==================== SLIPPAGE CALCULATOR ====================

def calculate_slippage(orderbook: Dict, size_usd: float, side: str = 'buy') -> Optional[Dict]:
    """
    Calculate slippage for market order
    Based on: https://github.com/i-ghz/algoliquidite
    """
    if side == 'buy':
        levels = sorted(orderbook['asks'], key=lambda x: x['price'])
    else:
        levels = sorted(orderbook['bids'], key=lambda x: x['price'], reverse=True)
    
    if not levels:
        return None
    
    best_bid = max([b['price'] for b in orderbook['bids']])
    best_ask = min([a['price'] for a in orderbook['asks']])
    mid_price = (best_bid + best_ask) / 2
    best_price = best_ask if side == 'buy' else best_bid
    
    # For buy: spend size_usd to get coins
    # For sell: sell coins worth size_usd (at mid price) to get USD
    remaining = size_usd
    total_qty = 0
    total_cost = 0
    levels_used = 0
    worst_price = best_price
    
    for level in levels:
        if remaining <= 0:
            break
        
        price = level['price']
        qty_available = level['qty']
        
        if qty_available <= 0 or price <= 0:
            continue
        
        levels_used += 1
        worst_price = price
        
        if side == 'buy':
            # Buy side: spend USD to get coins
            value_at_level = qty_available * price
            
            if remaining <= value_at_level:
                # Can fulfill order at this level
                qty_taken = remaining / price
                total_qty += qty_taken
                total_cost += remaining
                remaining = 0
                break
            else:
                # Take all available at this level
                total_qty += qty_available
                total_cost += value_at_level
                remaining -= value_at_level
        else:
            # Sell side: sell coins to get USD
            # Convert USD size to coin amount at mid price
            if levels_used == 1:  # First iteration, calculate coin amount
                coin_amount = size_usd / mid_price
                remaining = coin_amount
            
            if remaining <= qty_available:
                # Can fulfill order at this level
                value = remaining * price
                total_qty += remaining
                total_cost += value
                remaining = 0
                break
            else:
                # Take all available at this level
                value = qty_available * price
                total_qty += qty_available
                total_cost += value
                remaining -= qty_available
    
    # Check if order was filled
    if remaining > 0.0001:  # Allow tiny rounding errors
        filled_pct = ((size_usd - remaining) / size_usd) * 100 if side == 'buy' else ((total_cost / size_usd) * 100)
        return {
            'filled': False,
            'slippage_bps': None,
            'filled_percent': round(filled_pct, 2)
        }
    
    if total_qty == 0:
        return None
    
    # Calculate average execution price and slippage
    avg_price = total_cost / total_qty
    
    # Slippage calculation
    if side == 'buy':
        slippage = ((avg_price - mid_price) / mid_price) * 100
    else:
        slippage = ((mid_price - avg_price) / mid_price) * 100
    
    slippage_bps = slippage * 100
    
    # Effective spread (from best to worst price traversed)
    effective_spread_bps = abs((worst_price - best_price) / best_price) * 10000
    
    return {
        'filled': True,
        'slippage_bps': round(slippage_bps, 2),
        'effective_spread_bps': round(effective_spread_bps, 2),
        'levels_used': levels_used,
        'avg_price': round(avg_price, 6),
        'best_price': round(best_price, 6),
        'worst_price': round(worst_price, 6)
    }


# ==================== COMPARISON ====================

def compare_asset(asset: str, order_sizes: List[int]) -> Dict:
    """Compare asset across all DEXes"""
    print(f"\n{'='*140}")
    print(f"📊 {asset} - {ALL_ASSETS[asset]['cat'].upper()}")
    print('='*140)
    
    config = ALL_ASSETS[asset]
    category = config['cat']
    
    # Fetch orderbooks
    print(f"\n🔄 Fetching orderbooks...")
    
    hl_book = HyperliquidClient.get_orderbook(config['hl'])
    if hl_book:
        print(f"  ✅ Hyperliquid ({config['hl']}): ${hl_book['mid_price']:.4f}, {hl_book['spread_bps']:.2f} bps")
    
    lt_book = LighterClient.get_orderbook(config['lt'])
    if lt_book:
        print(f"  ✅ Lighter ({config['lt']}): ${lt_book['mid_price']:.4f}, {lt_book['spread_bps']:.2f} bps")
    
    # Ostium
    os_data = OstiumClient.get_data(config['os'], category)
    if os_data and os_data.get('oracle_price'):
        print(f"  ✅ Ostium ({config['os']}): ${os_data['oracle_price']:.4f} oracle")
    else:
        print(f"  ✅ Ostium ({config['os']}): Using fee structure")
    
    # Avantis
    av_fees = FEES['avantis'].get(category, FEES['avantis']['equities'])
    is_zero_slip = config['av'] in AVANTIS_ZERO_SLIPPAGE
    print(f"  ✅ Avantis ({config['av']}): {'Zero slippage ⭐' if is_zero_slip else 'Fixed-fee'}")
    
    print(f"\n{'─'*140}")
    print(f"{'Size':<15} {'DEX':<25} {'Mid':<12} {'Spread':<9} {'Slip':<9} {'Fee':<9} {'Total':<9} {'Fee $':<12}")
    print('─'*140)
    
    results = {}
    
    for size in order_sizes:
        size_results = []
        
        # Hyperliquid
        if hl_book:
            buy_slip = calculate_slippage(hl_book, size, 'buy')
            sell_slip = calculate_slippage(hl_book, size, 'sell')
            
            # Check if we have valid slippage data (even partial fills)
            if buy_slip and sell_slip:
                # Use filled orders if available, otherwise use partial
                buy_filled = buy_slip.get('filled', False)
                sell_filled = sell_slip.get('filled', False)
                buy_bps = buy_slip.get('slippage_bps')
                sell_bps = sell_slip.get('slippage_bps')
                
                # Calculate average if we have at least one valid slippage
                if buy_bps is not None and sell_bps is not None:
                    avg_slip = (buy_bps + sell_bps) / 2
                    fee_bps = FEES['hyperliquid']['taker']
                    total_bps = avg_slip + fee_bps
                    fee_usd = size * (fee_bps / 10000)
                    
                    status = ""
                    if not buy_filled or not sell_filled:
                        fill_pct = min(
                            buy_slip.get('filled_percent', 100),
                            sell_slip.get('filled_percent', 100)
                        )
                        status = f" ({fill_pct:.0f}% filled)"
                    
                    print(f"${size:>13,}  {'Hyperliquid':<25} ${hl_book['mid_price']:<11.2f} {hl_book['spread_bps']:>7.2f}  {avg_slip:>7.2f}  {fee_bps:>7.2f}  {total_bps:>7.2f}  ${fee_usd:>10.2f}{status}")
                    size_results.append({
                        'dex': 'Hyperliquid',
                        'total_bps': total_bps,
                        'fee_usd': fee_usd,
                        'partial': not (buy_filled and sell_filled)
                    })
                elif buy_bps is not None:
                    # Only buy side has data
                    avg_slip = buy_bps
                    fee_bps = FEES['hyperliquid']['taker']
                    total_bps = avg_slip + fee_bps
                    fee_usd = size * (fee_bps / 10000)
                    fill_pct = buy_slip.get('filled_percent', 100)
                    
                    print(f"${size:>13,}  {'Hyperliquid':<25} ${hl_book['mid_price']:<11.2f} {hl_book['spread_bps']:>7.2f}  {avg_slip:>7.2f}  {fee_bps:>7.2f}  {total_bps:>7.2f}  ${fee_usd:>10.2f} (buy only, {fill_pct:.0f}%)")
                    size_results.append({
                        'dex': 'Hyperliquid',
                        'total_bps': total_bps,
                        'fee_usd': fee_usd,
                        'partial': True
                    })
                else:
                    print(f"${size:>13,}  {'Hyperliquid':<25} ⚠️  Insufficient liquidity")
            else:
                print(f"${size:>13,}  {'Hyperliquid':<25} ⚠️  No orderbook data")
        
        # Lighter
        if lt_book:
            buy_slip = calculate_slippage(lt_book, size, 'buy')
            sell_slip = calculate_slippage(lt_book, size, 'sell')
            
            # Check if we have valid slippage data (even partial fills)
            if buy_slip and sell_slip:
                buy_filled = buy_slip.get('filled', False)
                sell_filled = sell_slip.get('filled', False)
                buy_bps = buy_slip.get('slippage_bps')
                sell_bps = sell_slip.get('slippage_bps')
                
                # Calculate average if we have at least one valid slippage
                if buy_bps is not None and sell_bps is not None:
                    avg_slip = (buy_bps + sell_bps) / 2
                    fee_bps = FEES['lighter']['taker']
                    total_bps = avg_slip + fee_bps
                    fee_usd = size * (fee_bps / 10000)
                    
                    status = ""
                    if not buy_filled or not sell_filled:
                        fill_pct = min(
                            buy_slip.get('filled_percent', 100),
                            sell_slip.get('filled_percent', 100)
                        )
                        status = f" ({fill_pct:.0f}% filled)"
                    
                    print(f"{'':>15} {'Lighter':<25} ${lt_book['mid_price']:<11.2f} {lt_book['spread_bps']:>7.2f}  {avg_slip:>7.2f}  {fee_bps:>7.2f}  {total_bps:>7.2f}  ${fee_usd:>10.2f}{status}")
                    size_results.append({
                        'dex': 'Lighter',
                        'total_bps': total_bps,
                        'fee_usd': fee_usd,
                        'partial': not (buy_filled and sell_filled)
                    })
                elif buy_bps is not None:
                    # Only buy side has data
                    avg_slip = buy_bps
                    fee_bps = FEES['lighter']['taker']
                    total_bps = avg_slip + fee_bps
                    fee_usd = size * (fee_bps / 10000)
                    fill_pct = buy_slip.get('filled_percent', 100)
                    
                    print(f"{'':>15} {'Lighter':<25} ${lt_book['mid_price']:<11.2f} {lt_book['spread_bps']:>7.2f}  {avg_slip:>7.2f}  {fee_bps:>7.2f}  {total_bps:>7.2f}  ${fee_usd:>10.2f} (buy only, {fill_pct:.0f}%)")
                    size_results.append({
                        'dex': 'Lighter',
                        'total_bps': total_bps,
                        'fee_usd': fee_usd,
                        'partial': True
                    })
                else:
                    print(f"{'':>15} {'Lighter':<25} ⚠️  Insufficient liquidity")
            else:
                print(f"{'':>15} {'Lighter':<25} ⚠️  No orderbook data")
        
        # Ostium
        if os_data:
            ref_mid = os_data.get('oracle_price') or (hl_book or lt_book)['mid_price'] if (hl_book or lt_book) else 100
            os_spread = os_data['spread_bps']
            os_fee = os_data['opening_fee_bps']
            os_total = os_spread + os_fee
            os_fee_usd = size * (os_fee / 10000) + os_data['oracle_fee']
            
            print(f"{'':>15} {'Ostium':<25} ${ref_mid:<11.2f} {os_spread:>7.2f}  {'~0.00':>7}  {os_fee:>7.2f}  {os_total:>7.2f}  ${os_fee_usd:>10.2f}")
            size_results.append({'dex': 'Ostium', 'total_bps': os_total, 'fee_usd': os_fee_usd})
        
        # Avantis
        av_spread = 0 if is_zero_slip else 2.0
        av_opening = av_fees['opening']
        av_total = av_spread + av_opening
        av_fee_usd = size * (av_opening / 10000)
        note = " ⭐" if is_zero_slip else ""
        
        print(f"{'':>15} {'Avantis':<25} ${'N/A':<11} {av_spread:>7.2f}  {'~0.00':>7}  {av_opening:>7.2f}  {av_total:>7.2f}  ${av_fee_usd:>10.2f}{note}")
        size_results.append({'dex': 'Avantis', 'total_bps': av_total, 'fee_usd': av_fee_usd})
        
        print()
        results[size] = size_results
    
    return results


# ==================== INTERACTIVE ====================

def interactive_mode():
    print("\n" + "="*140)
    print("💸 MULTI-DEX RWA COMPARISON - Focused Assets")
    print("="*140)
    
    print("\n📊 Asset Categories:")
    print(f"  1. Gold & Silver (2 assets)")
    print(f"  2. Mag7 Stocks ({len(MAG7)} assets): {', '.join(MAG7)}")
    print(f"  3. HOOD Stock (1 asset)")
    print(f"  4. Indices (SPY, QQQ)")
    print(f"  5. Forex (EURUSD, USDJPY, GBPUSD)")
    print(f"  6. All Assets ({len(ALL_ASSETS)} total)")
    print(f"  7. Custom selection")
    
    choice = input("\nSelect category (1-7): ").strip()
    
    if choice == '1':
        selected = ['GOLD', 'SILVER']
    elif choice == '2':
        selected = MAG7
    elif choice == '3':
        selected = ['HOOD']
    elif choice == '4':
        selected = ['SPY', 'QQQ']
    elif choice == '5':
        selected = ['EURUSD', 'USDJPY', 'GBPUSD']
    elif choice == '6':
        selected = list(ALL_ASSETS.keys())
    elif choice == '7':
        custom = input("Enter assets (comma-separated, e.g., AAPL,GOLD,SPY): ").strip().upper()
        selected = [a.strip() for a in custom.split(',') if a.strip() in ALL_ASSETS]
    else:
        print("Invalid choice, using Mag7")
        selected = MAG7
    
    print(f"\n💰 Order Sizes:")
    print(f"  1. $10K only")
    print(f"  2. $100K only")
    print(f"  3. $1M only")
    print(f"  4. All sizes ($10K, $100K, $1M, $10M)")
    
    size_choice = input("\nSelect (default: 4): ").strip() or "4"
    
    if size_choice == "1":
        sizes = [10_000]
    elif size_choice == "2":
        sizes = [100_000]
    elif size_choice == "3":
        sizes = [1_000_000]
    else:
        sizes = ORDER_SIZES
    
    print(f"\n📊 Analyzing {len(selected)} assets across {len(sizes)} order sizes...\n")
    
    all_results = {}
    for asset in selected:
        if asset in ALL_ASSETS:
            results = compare_asset(asset, sizes)
            all_results[asset] = results
            time.sleep(0.5)
    
    # Summary
    print("\n\n" + "="*140)
    print("📈 SUMMARY - CHEAPEST DEX PER ASSET")
    print("="*140)
    
    for size in sizes:
        print(f"\n💰 ${size:,} Orders:")
        print(f"{'Asset':<12} {'Cheapest':<25} {'Total (bps)':<15} {'Savings'}")
        print('─'*80)
        
        for asset, size_results in all_results.items():
            if size in size_results:
                valid = [r for r in size_results[size] if 'total_bps' in r]
                if valid:
                    sorted_res = sorted(valid, key=lambda x: x['total_bps'])
                    cheapest = sorted_res[0]
                    savings = f"{sorted_res[1]['total_bps'] - cheapest['total_bps']:.2f} bps" if len(sorted_res) > 1 else ""
                    print(f"{asset:<12} {cheapest['dex']:<25} {cheapest['total_bps']:>13.2f}  {savings}")
    
    print("\n💡 INSIGHTS:")
    print("  • ⭐ = Zero slippage (Avantis)")
    print("  • Lighter: 0% fees (best for most cases)")
    print("  • Hyperliquid: 4.5 bps taker (CORRECTED)")
    print("  • Ostium: 3-15 bps + $0.10 oracle")
    print("  • Avantis: 3-6.35 bps, zero slippage on major pairs")


def main():
    print("""
╔════════════════════════════════════════════════════════════════════════════════╗
║           MULTI-DEX RWA COMPARISON - FOCUSED ASSETS                            ║
║           Gold, Silver, Mag7, HOOD, Indices, Forex                             ║
╚════════════════════════════════════════════════════════════════════════════════╝

📊 Features:
   • Hyperliquid: 4.5 bps taker fee
   • Lighter: 0 bps (zero fee)
   • Ostium: SDK support + REST API fallback
   • Avantis: Fixed-fee perpetuals

💡 To use Ostium SDK, set environment variables:
   export OSTIUM_PRIVATE_KEY="your_private_key"
   export OSTIUM_RPC_URL="https://arb1.arbitrum.io/rpc"
    """)

    
    try:
        # Initialize Ostium SDK if available
        if OSTIUM_SDK_AVAILABLE:
            OstiumClient.initialize_sdk()
        
        interactive_mode()
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()