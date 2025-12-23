#!/usr/bin/env python3
"""
Multi-DEX Perpetual Cost Comparison Tool
Compare execution costs across Hyperliquid, Lighter, Ostium, and Avantis
"""

import sys
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants

# Initialize the Hyperliquid Info client
info = Info(constants.MAINNET_API_URL)

# Fee structures for different DEXes
DEX_FEES = {
    'hyperliquid': {
        'taker': 0.00035,  # 0.035%
        'maker': 0.0001,   # 0.01%
        'name': 'Hyperliquid',
        'has_api': True
    },
    'lighter': {
        'taker': 0.0,      # 0% (zero-fee in beta)
        'maker': 0.0,      # 0%
        'name': 'Lighter',
        'has_api': False,  # API exists but not integrated yet
        'note': 'Zero fees during Season 2'
    },
    'ostium': {
        'opening': 0.001,  # ~0.1% opening fee (estimated)
        'rollover': 0.00008, # ~0.008%/day holding fee
        'name': 'Ostium',
        'has_api': False,
        'note': 'Opening + daily rollover fees'
    },
    'avantis': {
        'taker': 0.0,      # Zero-fee perpetuals
        'profit_fee': 0.10, # 10% of profit (estimated)
        'maker': 0.0,
        'name': 'Avantis',
        'has_api': True,
        'note': 'Only pay fee on profitable trades (~10% of profit)'
    }
}


def calculate_multi_dex_comparison(coin='BTC', dollar_amounts=None, hold_days=1):
    """Compare execution costs across multiple DEXes"""
    try:
        if dollar_amounts is None:
            dollar_amounts = [10000, 100000, 1000000, 10000000]
        
        print(f'\n💸 Multi-DEX Cost Comparison for {coin}')
        print(f'📅 Holding Period: {hold_days} day(s)\n')
        
        # Fetch Hyperliquid orderbook
        orderbook = info.l2_snapshot(coin)
        bids = orderbook['levels'][0]
        asks = orderbook['levels'][1]
        
        # Calculate mid price
        best_bid = float(bids[0]['px'])
        best_ask = float(asks[0]['px'])
        mid_price = (best_bid + best_ask) / 2
        
        print(f'=== MARKET DATA (Hyperliquid) ===')
        print(f"Coin: {coin}")
        print(f"Mid Price: ${mid_price:,.2f}")
        print(f"Best Bid: ${best_bid:,.2f}")
        print(f"Best Ask: ${best_ask:,.2f}")
        print(f"Spread: ${best_ask - best_bid:.4f} ({((best_ask - best_bid) / mid_price * 100):.4f}%)\n")
        
        # BUY Orders Comparison
        print('=' * 120)
        print('🔴 BUY MARKET ORDER - TOTAL COST COMPARISON')
        print('=' * 120)
        print(f"{'Order Size':<15} {'DEX':<15} {'Slippage':<12} {'Opening Fee':<12} {'Daily Fee':<12} {'Total Cost':<15} {'vs Mid %':<10}")
        print('─' * 120)
        
        for dollar_size in dollar_amounts:
            # Calculate Hyperliquid execution
            remaining_dollars = dollar_size
            total_coins = 0
            total_cost = 0
            
            for level in asks:
                if remaining_dollars <= 0:
                    break
                level_size = float(level['sz'])
                level_price = float(level['px'])
                max_coins_at_level = remaining_dollars / level_price
                filled_coins = min(max_coins_at_level, level_size)
                cost = filled_coins * level_price
                total_coins += filled_coins
                total_cost += cost
                remaining_dollars -= cost
            
            if remaining_dollars > 0.01:
                print(f"${dollar_size:>13,}   ⚠️  INSUFFICIENT LIQUIDITY ON HYPERLIQUID")
                continue
            
            avg_exec_price = total_cost / total_coins
            slippage_dollars = (avg_exec_price - mid_price) * total_coins
            
            # Hyperliquid
            hl_fee = total_cost * DEX_FEES['hyperliquid']['taker']
            hl_total = total_cost + hl_fee
            hl_vs_mid = ((hl_total / (total_coins * mid_price)) - 1) * 100
            print(f"${dollar_size:>13,}  {'Hyperliquid':<15} ${slippage_dollars:<11,.2f} ${hl_fee:<11,.2f} ${0.00:<11.2f} ${hl_total:<14,.2f} {hl_vs_mid:>9.3f}%")
            
            # Lighter (zero fees)
            lt_total = total_cost
            lt_vs_mid = ((lt_total / (total_coins * mid_price)) - 1) * 100
            print(f"{'':>15} {'Lighter':<15} ${slippage_dollars:<11,.2f} ${0.00:<11.2f} ${0.00:<11.2f} ${lt_total:<14,.2f} {lt_vs_mid:>9.3f}%")
            
            # Ostium (opening + rollover fees)
            os_opening = total_cost * DEX_FEES['ostium']['opening']
            os_rollover = total_cost * DEX_FEES['ostium']['rollover'] * hold_days
            os_total = total_cost + os_opening + os_rollover
            os_vs_mid = ((os_total / (total_coins * mid_price)) - 1) * 100
            print(f"{'':>15} {'Ostium':<15} ${slippage_dollars:<11,.2f} ${os_opening:<11,.2f} ${os_rollover:<11,.2f} ${os_total:<14,.2f} {os_vs_mid:>9.3f}%")
            
            # Avantis (zero opening, assume 10% profit fee on 5% gain)
            av_opening = 0
            av_total_opening = total_cost
            av_vs_mid = ((av_total_opening / (total_coins * mid_price)) - 1) * 100
            print(f"{'':>15} {'Avantis':<15} ${slippage_dollars:<11,.2f} ${av_opening:<11.2f} ${'N/A':<11} ${av_total_opening:<14,.2f} {av_vs_mid:>9.3f}%")
            print()
        
        # SELL Orders Comparison
        print('=' * 120)
        print('🟢 SELL MARKET ORDER - NET RECEIVED COMPARISON')
        print('=' * 120)
        print(f"{'Order Size':<15} {'DEX':<15} {'Slippage':<12} {'Closing Fee':<12} {'Daily Fee':<12} {'Net Received':<15} {'vs Mid %':<10}")
        print('─' * 120)
        
        for dollar_size in dollar_amounts:
            target_coins = dollar_size / mid_price
            remaining_coins = target_coins
            total_value = 0
            
            for level in bids:
                if remaining_coins <= 0:
                    break
                level_size = float(level['sz'])
                level_price = float(level['px'])
                filled_coins = min(remaining_coins, level_size)
                value = filled_coins * level_price
                total_value += value
                remaining_coins -= filled_coins
            
            if remaining_coins > 0.000001:
                print(f"${dollar_size:>13,}   ⚠️  INSUFFICIENT LIQUIDITY ON HYPERLIQUID")
                continue
            
            avg_exec_price = total_value / target_coins
            slippage_dollars = (mid_price - avg_exec_price) * target_coins
            
            # Hyperliquid
            hl_fee = total_value * DEX_FEES['hyperliquid']['taker']
            hl_net = total_value - hl_fee
            hl_vs_mid = ((hl_net / (target_coins * mid_price)) - 1) * 100
            print(f"${dollar_size:>13,}  {'Hyperliquid':<15} ${slippage_dollars:<11,.2f} ${hl_fee:<11,.2f} ${0.00:<11.2f} ${hl_net:<14,.2f} {hl_vs_mid:>9.3f}%")
            
            # Lighter (zero fees)
            lt_net = total_value
            lt_vs_mid = ((lt_net / (target_coins * mid_price)) - 1) * 100
            print(f"{'':>15} {'Lighter':<15} ${slippage_dollars:<11,.2f} ${0.00:<11.2f} ${0.00:<11.2f} ${lt_net:<14,.2f} {lt_vs_mid:>9.3f}%")
            
            # Ostium (no closing fee except liquidation, but rollover applies)
            os_rollover = total_value * DEX_FEES['ostium']['rollover'] * hold_days
            os_net = total_value - os_rollover
            os_vs_mid = ((os_net / (target_coins * mid_price)) - 1) * 100
            print(f"{'':>15} {'Ostium':<15} ${slippage_dollars:<11,.2f} ${0.00:<11.2f} ${os_rollover:<11,.2f} ${os_net:<14,.2f} {os_vs_mid:>9.3f}%")
            
            # Avantis (zero closing fee)
            av_net = total_value
            av_vs_mid = ((av_net / (target_coins * mid_price)) - 1) * 100
            print(f"{'':>15} {'Avantis':<15} ${slippage_dollars:<11,.2f} ${0.00:<11.2f} ${'N/A':<11} ${av_net:<14,.2f} {av_vs_mid:>9.3f}%")
            print()
        
        # Summary and notes
        print('\n' + '=' * 120)
        print('📊 DEX COMPARISON SUMMARY')
        print('=' * 120)
        
        for dex_key, dex_info in DEX_FEES.items():
            print(f"\n🔹 {dex_info['name']}:")
            if 'taker' in dex_info:
                print(f"   • Taker Fee: {dex_info['taker']*100:.3f}%")
            if 'maker' in dex_info:
                print(f"   • Maker Fee: {dex_info['maker']*100:.3f}%")
            if 'opening' in dex_info:
                print(f"   • Opening Fee: {dex_info['opening']*100:.3f}%")
            if 'rollover' in dex_info:
                print(f"   • Daily Rollover: {dex_info['rollover']*100:.4f}%")
            if 'profit_fee' in dex_info:
                print(f"   • Profit Fee: {dex_info['profit_fee']*100:.1f}% of gains")
            if 'note' in dex_info:
                print(f"   • Note: {dex_info['note']}")
            if 'has_api' in dex_info:
                print(f"   • API Available: {'✅ Yes' if dex_info['has_api'] else '⚠️  Not yet integrated'}")
        
        print('\n💡 KEY INSIGHTS:')
        print('   • Slippage is the SAME across all DEXes (based on Hyperliquid orderbook)')
        print('   • Lighter & Avantis offer zero opening/closing fees')
        print('   • Hyperliquid has the most competitive fee structure for active traders')
        print('   • Ostium charges daily rollover fees - costs increase with holding time')
        print('   • Avantis only charges fees on profitable trades (~10% of profit)')
        print('   • For frequent traders: Hyperliquid or Lighter are best')
        print('   • For long-term holders: Watch out for Ostium rollover fees')
        
        print('\n⚠️  IMPORTANT NOTES:')
        print('   • This comparison uses Hyperliquid orderbook for slippage estimates')
        print('   • Actual slippage may vary on each DEX based on their liquidity')
        print('   • Lighter and Ostium fees are estimates - check their official docs')
        print('   • Funding rates are NOT included in this comparison')
        print(f'   • Holding period assumed: {hold_days} day(s)')
        
        return {
            'mid_price': mid_price,
            'orderbook': orderbook
        }
        
    except Exception as e:
        print(f'❌ Error: {str(e)}')
        return None


def interactive_menu():
    """Interactive menu for user input"""
    print('=' * 60)
    print('💸 MULTI-DEX PERPETUAL COST COMPARISON TOOL')
    print('=' * 60)
    print('\nCompare execution costs across:')
    print('  • Hyperliquid (0.035% taker)')
    print('  • Lighter (0% fees)')
    print('  • Ostium (opening + rollover fees)')
    print('  • Avantis (zero-fee, profit-based)')
    
    coin = input('\nEnter coin symbol to analyze (e.g., BTC, ETH, PAXG): ').strip().upper()
    
    if not coin:
        print('❌ No coin symbol entered. Exiting.')
        return False
    
    # Ask for holding period
    hold_input = input('How many days will you hold the position? (default: 1): ').strip()
    hold_days = int(hold_input) if hold_input else 1
    
    # Ask for custom dollar amounts
    print('\nDefault order sizes: $10k, $100k, $1M, $10M')
    custom = input('Press Enter for defaults, or enter custom amounts (e.g., 5000,50000,500000): ').strip()
    
    if custom:
        try:
            dollar_amounts = [float(x.strip()) for x in custom.split(',')]
            calculate_multi_dex_comparison(coin, dollar_amounts, hold_days)
        except ValueError:
            print('❌ Invalid format. Using default sizes.')
            calculate_multi_dex_comparison(coin, hold_days=hold_days)
    else:
        calculate_multi_dex_comparison(coin, hold_days=hold_days)
    
    # Ask if user wants to analyze another pair
    print('\n' + '─' * 60)
    continue_choice = input('Compare another pair? (y/n): ').strip().lower()
    return continue_choice == 'y'


def main():
    """Main execution function"""
    args = sys.argv[1:]
    
    if not args:
        # No arguments: run interactive mode
        while True:
            should_continue = interactive_menu()
            if not should_continue:
                break
    elif args[0] == 'compare':
        # Direct comparison
        coin = args[1] if len(args) > 1 else 'BTC'
        hold_days = int(args[2]) if len(args) > 2 else 1
        if len(args) > 3:
            dollar_amounts = [float(x) for x in args[3].split(',')]
            calculate_multi_dex_comparison(coin, dollar_amounts, hold_days)
        else:
            calculate_multi_dex_comparison(coin, hold_days=hold_days)
    else:
        print('Usage:')
        print('  python orderbook.py                    # Interactive mode')
        print('  python orderbook.py compare BTC        # Compare BTC with defaults')
        print('  python orderbook.py compare BTC 7      # BTC with 7-day holding')
        print('  python orderbook.py compare BTC 1 10000,100000  # Custom sizes')


if __name__ == '__main__':
    main()