import os
import json
import random
import time
from datetime import datetime
from smartapi import SmartConnect

# --- AGENT CONFIGURATION & MEMORY SETUP ---
INITIAL_CAPITAL = 10000.00
LOSS_THRESHOLD_FOR_ADAPTATION = INITIAL_CAPITAL * 0.25 
# Cloud Run allows /tmp for temporary storage between calls (session management)
STATE_FILE = "/tmp/agent_state.json" 
LOT_SIZE = 50 

# --- UTILITY: STATE AND LOGGING ---

def load_state():
    """Loads the agent's memory (state) from a local file or creates a default state."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    
    # Default initial state (Agent's initial memory)
    return {
        "capital": INITIAL_CAPITAL,
        "strategy_version": 1.0,
        "total_losses": 0.0,
        "positions": [],
        "trade_id_counter": 0
    }

def save_state(state):
    """Saves the agent's memory (state) to a local file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"ERROR: Could not save state. {e}")

# --- ANGEL ONE TOOL FUNCTIONS (INTEGRATION POINTS) ---

def connect_angel_one():
    """Initializes and returns the authenticated Angel One connection object."""
    try:
        # Load credentials from secure environment variables
        api_key = os.environ.get('ANGELONE_API_KEY')
        client_id = os.environ.get('ANGELONE_CLIENT_ID')
        # NOTE: Full production code requires handling TOTP or session tokens here
        
        if not api_key or not client_id:
            print("ERROR: Angel One credentials not found in environment variables.")
            return None
        
        # This is where the SmartAPI login/session creation code would go
        obj = SmartConnect(api_key=api_key)
        # Assuming successful login and session object is returned
        return obj 
    except Exception as e:
        print(f"Angel One Connection Error: {e}")
        return None 

def get_live_nifty_price(client):
    """MOCK: Retrieves live Nifty 50 Spot price via Angel One API. Replace with real SDK call."""
    # In production: client.ltp("NSE", "NIFTY")
    # Using fluctuating time-based mock data to prove logic works
    price_base = 23000
    volatility = random.uniform(-100, 100) 
    return price_base + volatility

def place_order(client, symbol, lots, action):
    """MOCK: Places an order via Angel One API. Replace with real SDK call."""
    
    # Simulate the premium and cost
    PREMIUM_SIMULATION = random.uniform(100, 200)
    cost = PREMIUM_SIMULATION * lots * LOT_SIZE

    # Simulate market movement and rejection chance
    if random.random() < 0.1: 
        return {"status": "REJECTED", "error": "Simulated Slippage/Margin failure"}
        
    return {
        "status": "EXECUTED",
        "order_id": f"ORD_{int(time.time() * 1000)}",
        "entry_cost": cost,
        "entry_premium": PREMIUM_SIMULATION
    }

# --- CORE ADAPTIVE LOGIC ---

def quant_agent_logic(state, client):
    """The central decision-making function."""
    
    log_messages = []
    
    # --- 1. THE CRITICAL ADAPTATION CHECK (The Intelligence) ---
    if state['total_losses'] >= LOSS_THRESHOLD_FOR_ADAPTATION and state['strategy_version'] < 2.0:
        state['strategy_version'] = 2.0
        log_messages.append(f"**ADAPTATION: CRITICAL** Total losses (₹{state['total_losses']:.2f}) exceeded 25% threshold.")
        log_messages.append(f"Switching to **Strategy 2.0: Risk Management (10% max risk)**.")
        state['total_losses'] = 0.0 # Reset loss counter for new strategy evaluation
    
    # --- 2. EXECUTE EXIT LOGIC (Risk Management) ---
    # Simplified Exit Logic: Close all positions after 3 cycles (simulating time/SL hit)
    closed_trades = []
    
    # Logic to check existing positions and close based on PnL/SL/TP goes here
    # For now, we simulate a small PnL and close one position if open
    if state['positions'] and random.random() < 0.5:
        pos = state['positions'].pop(0) 
        PnL = pos['entry_cost'] * (random.uniform(-0.15, 0.20)) # Simulating PnL
        state['capital'] += pos['entry_cost'] + PnL
        state['total_losses'] += (abs(PnL) if PnL < 0 else 0)
        log_messages.append(f"CLOSE: Trade {pos['id']} completed ({pos['type']}). PnL: ₹{PnL:.2f}.")

    # --- 3. EXECUTE ENTRY LOGIC ---
    
    current_nifty_price = get_live_nifty_price(client)
    available_capital = state['capital']
    
    # Simple signal: trade CE if price > base, PE if price < base
    signal = 'BUY_CE' if current_nifty_price > 23000 else 'BUY_PE'
    
    if len(state['positions']) == 0: 
        lots_to_buy = 1
        
        if state['strategy_version'] == 1.0:
            # V1.0 (Dumb) - Risks maximum capital
            max_afford = available_capital / 7500 
            lots_to_buy = max(1, int(max_afford))
            log_messages.append(f"DUMB_TRADE: Strategy 1.0 buying {lots_to_buy} lots (High Risk).")
            
        elif state['strategy_version'] == 2.0:
            # V2.0 (Intelligent) - Applies max 10% risk rule
            MAX_RISK_CAPITAL = INITIAL_CAPITAL * 0.10
            # Assume 1 lot is maximum allowed under 10% risk budget
            lots_to_buy = max(1, int(MAX_RISK_CAPITAL / 7500)) 
            log_messages.append(f"SMART_TRADE: Strategy 2.0 buying {lots_to_buy} lot(s). (10% Risk).")

        
        order_result = place_order(client, "NIFTY", lots_to_buy, "BUY")
        
        if order_result["status"] == "EXECUTED":
            state['trade_id_counter'] += 1
            new_position = {
                "id": state['trade_id_counter'],
                "entry_cost": order_result["entry_cost"],
                "entry_premium": order_result["entry_premium"],
                "lots": lots_to_buy,
                "type": signal,
                "entry_time": datetime.now().isoformat()
            }
            state['positions'].append(new_position)
            state['capital'] -= order_result["entry_cost"]
            log_messages.append(f"OPEN: Trade {new_position['id']} placed. Capital: ₹{state['capital']:.2f}.")
        else:
             log_messages.append(f"ERROR: Order rejected. {order_result['error']}.")

    return state, log_messages

# --- CLOUD RUN ENTRY POINT ---

def quant_agent_entry(request):
    """
    Entry point for the Cloud Run Service (triggered via HTTP POST from Cloud Scheduler).
    """
    # 1. Connect to Broker
    # NOTE: You MUST replace 'None' with the actual authenticated Angel One client object
    angel_client = None 

    # 2. Load Agent's Memory
    state = load_state()
    
    # 3. Execute Adaptive Logic
    new_state, logs = quant_agent_logic(state, angel_client)
    
    # 4. Save Agent's Memory (Crucial for adaptation across executions)
    save_state(new_state)
    
    # 5. Print Log (Captured by Google Cloud Logging)
    response_logs = ["Quant Agent Cycle Completed:"]
    response_logs.extend(logs)
    response_logs.append(f"FINAL CAPITAL: ₹{new_state['capital']:.2f}")

    # Print to console for GCP logging
    for log in response_logs:
        print(log) 

    # Return a success message (required for Cloud Run to terminate correctly)
    return "\n".join(response_logs), 200
