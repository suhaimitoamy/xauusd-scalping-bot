import os
import sys
import json
import time
import subprocess
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_cmd(cmd):
    print(f"\n[RUNNING] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}")
        print(result.stdout)
        print(result.stderr)
    return result

def get_next_month(current, end_month, start_month):
    year = int(current[:4])
    month = int(current[4:])
    month += 1
    if month > 12:
        month = 1
        year += 1
    next_m = f"{year}{month:02d}"
    if next_m > end_month:
        return start_month
    return next_m

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-month', type=str, default="202501", help='Start month (e.g. 202501)')
    parser.add_argument('--end-month', type=str, default="202605", help='End month (e.g. 202605)')
    parser.add_argument('--resume-month', type=str, help='Month to start the loop from (e.g. 202603)')
    parser.add_argument('--initial-balance', type=float, default=3000, help='Initial virtual balance')
    parser.add_argument('--risk-percent', type=float, default=1.0, help='Risk percentage per trade')
    parser.add_argument('--target-profit-pct', type=float, default=20.0, help='Target Net Profit percentage to stop loop (e.g. 300 for 300%)')
    parser.add_argument('--max-cycles', type=int, default=50, help='Max cycles before stopping')
    
    args = parser.parse_args()
    
    os.makedirs("brain_versions/full_cycle_reports", exist_ok=True)
    
    best_wr = 0
    best_balance = 0
    best_cycle = 0
    best_brain_path = None
    best_drawdown = 0
    best_net_pl = 0
    
    current_sandbox_brain = "brain_versions/sandbox_brain_current.json"
    
    current_month = args.resume_month if args.resume_month else args.start_month
    current_balance = args.initial_balance
    
    for cycle in range(1, args.max_cycles + 1):
        print("\n" + "="*60)
        print(f"🚀 STARTING CYCLE {cycle:03d} / {args.max_cycles} (MONTH: {current_month})")
        print("="*60)
        
        # 1. SIMULATION
        sim_cmd = [
            sys.executable, "src/run_simulator.py",
            "--month", current_month,
            "--keep-ghost",
            "--initial-balance", str(current_balance),
            "--risk-percent", str(args.risk_percent),
            "--replace-month"
        ]
        
        if os.path.exists(current_sandbox_brain):
            sim_cmd.extend(["--sandbox-brain", current_sandbox_brain])
            
        sim_type = "MAIN"
            
        res = run_cmd(sim_cmd)
        if res.returncode != 0:
            print("[ABORT] Simulation failed.")
            sys.exit(1)
            
        # Parse virtual sim report
        try:
            with open("data/virtual_sim_report.json", "r") as f:
                sim_report = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to read sim report: {e}")
            sys.exit(1)
            
        wr = sim_report['winrate']
        balance = sim_report['ending_balance']
        sim_id = sim_report['simulation_id']
        
        net_pl_pct = sim_report['net_pl_pct']
        print(f"Cycle {cycle:03d} Results: WR: {wr:.2f}% | Balance: ${balance:.2f} | P/L: {net_pl_pct:+.2f}%")
        
        # Track best (now based on Net P/L Pct instead of WR)
        if net_pl_pct > best_net_pl or cycle == 1:
            best_wr = wr
            best_balance = balance
            best_cycle = cycle
            best_drawdown = sim_report['max_dd_pct']
            best_net_pl = net_pl_pct
            
            # Save best result json
            best_result = {
                "best_cycle": best_cycle,
                "best_month": current_month,
                "best_wr": best_wr,
                "best_ending_balance": best_balance,
                "best_drawdown": best_drawdown,
                "best_net_pl_pct": best_net_pl,
                "target_achieved": best_net_pl >= args.target_profit_pct
            }
            with open("brain_versions/best_cycle_result.json", "w") as f:
                json.dump(best_result, f, indent=4)
        
        current_balance = balance # Update rolling balance
        
        if net_pl_pct >= args.target_profit_pct:
            print(f"\n🎉 TARGET PROFIT ({args.target_profit_pct}%) ACHIEVED FOR THIS MONTH! 🎉")
            # We don't break, we keep rolling forward with this good brain
            
        if cycle == args.max_cycles:
            print("\n⚠️ MAX CYCLES REACHED. STOPPING.")
            break
            
        # 2. AI RESEARCH
        # AI looks at everything in MAIN (which accumulates our rolling months)
        research_cmd = [sys.executable, "src/ghost_trade_research.py", "--sim-type", "MAIN"]
        res = run_cmd(research_cmd)
        if res.returncode != 0:
            print("[ABORT] AI Research failed.")
            sys.exit(1)
            
        # Extract candidate JSON path from output
        # E.g. "SUCCESS! AI candidates saved to: brain_versions/ai_method_candidates_20260607_012345.json"
        candidate_file = None
        for line in res.stdout.split('\n'):
            if "SUCCESS! AI candidates saved to:" in line:
                candidate_file = line.split("SUCCESS! AI candidates saved to:")[1].strip()
                break
                
        if not candidate_file or not os.path.exists(candidate_file):
            print("[ERROR] Could not find generated candidate file.")
            sys.exit(1)
            
        # 3. CANDIDATE TESTER
        tester_cmd = [sys.executable, "src/candidate_method_tester.py"]
        run_cmd(tester_cmd)
        
        # Find latest test report
        reports = glob.glob("brain_versions/candidate_test_report_*.json")
        if not reports:
            print("[ERROR] No tester reports found.")
            sys.exit(1)
            
        latest_report = max(reports, key=os.path.getctime)
        with open(latest_report, "r") as f:
            tester_data = json.load(f)
            
        valid_methods = []
        rejected_reasons = []
        for r in tester_data.get('results', []):
            if r['file'] == candidate_file:
                for cand in r['candidates']:
                    if cand['status'] == 'TESTABLE':
                        valid_methods.append(cand['name'])
                    else:
                        rejected_reasons.append(f"{cand['name']}: {cand['status']} ({cand['reason']})")
                        
        # Read the raw candidate file to extract valid JSON definitions
        with open(candidate_file, "r") as f:
            raw_cands = json.load(f)
            
        sandbox_methods_dict = {}
        
        # Keep old methods if any exist
        if current_sandbox_brain and os.path.exists(current_sandbox_brain):
            with open(current_sandbox_brain, "r") as f:
                old_brain = json.load(f)
                for m in old_brain.get('methods', []):
                    sandbox_methods_dict[m['name']] = m
                
        # Append new testable ones
        for m in raw_cands.get('methods', []):
            if m['name'] in valid_methods:
                sandbox_methods_dict[m['name']] = m
                
        sandbox_methods = list(sandbox_methods_dict.values())
        
        # Save new sandbox brain (Accumulate)
        with open(current_sandbox_brain, "w") as f:
            json.dump({"methods": sandbox_methods}, f, indent=4)
            
        print(f"[OK] Updated sandbox brain: {current_sandbox_brain} with {len(sandbox_methods)} methods")
        
        # Save Cycle Report
        cycle_report = {
            "cycle": cycle,
            "month": current_month,
            "simulation_id": sim_id,
            "starting_balance": sim_report['initial_balance'],
            "ending_balance": balance,
            "net_pl": sim_report['net_pl'],
            "net_pl_pct": sim_report['net_pl_pct'],
            "max_dd_pct": sim_report['max_dd_pct'],
            "winrate": wr,
            "total_trades": sim_report['total_trades'],
            "wins": sim_report['wins'],
            "losses": sim_report['losses'],
            "generated_candidates_file": candidate_file,
            "valid_candidates_added": valid_methods,
            "rejected_candidates": rejected_reasons
        }
        
        with open(f"brain_versions/full_cycle_reports/cycle_{cycle:03d}_report.json", "w") as f:
            json.dump(cycle_report, f, indent=4)
            
        # Move to next month
        current_month = get_next_month(current_month, args.end_month, args.start_month)
            
    print("\n" + "="*60)
    print("🏁 FULL CYCLE COMPLETE 🏁")
    print("="*60)
    print(f"Initial Balance     : ${args.initial_balance:.2f}")
    print(f"Final Balance       : ${current_balance:.2f}")
    print(f"Best Monthly P/L    : {best_net_pl:+.2f}%")
    print(f"Best Monthly WR     : {best_wr:.2f}%")
    print(f"Total Cycles Ran    : {cycle}")
    print("="*60)

if __name__ == "__main__":
    import glob # Import here to ensure it's available for the glob.glob call above
    main()
