#!/usr/bin/env python3
"""
BitVMX Hash Chain Wrapper
This wrapper properly uses BitVMX's built-in hash chain generation
instead of recreating it externally.
"""

import json
import subprocess
import struct
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class BitVMXExecutionResult:
    """Result from BitVMX execution with hash chain"""
    payout: int
    total_steps: int
    final_hash: str
    trace_output: List[str]
    checkpoints: List[Tuple[int, str]]  # For n-ary search optimization

def run_bitvmx_with_hash_chain(
    elf_path: str,
    input_hex: str,
    checkpoint_interval: int = 100
) -> Optional[BitVMXExecutionResult]:
    """
    Run BitVMX emulator and get its native hash chain output
    
    Args:
        elf_path: Path to the RISC-V ELF binary
        input_hex: Hex-encoded input data
        checkpoint_interval: Steps between checkpoints for n-ary search
    
    Returns:
        BitVMXExecutionResult with hash chain data
    """
    
    # Run BitVMX with trace output (includes hash chain)
    cmd = [
        "./BitVMX-CPU/target/release/emulator",
        "execute",
        "--elf", elf_path,
        "--input", input_hex,
        "--trace",  # This outputs the trace with hashes
        "--checkpoints",  # Enable checkpoint output
        "--stdout"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"BitVMX execution failed: {e.stderr}")
        return None
    
    # Parse the output
    lines = result.stdout.strip().split('\n')
    trace_lines = []
    checkpoints = []
    payout = 0
    total_steps = 0
    final_hash = ""
    
    # Also check stderr for trace output
    if result.stderr:
        stderr_lines = result.stderr.strip().split('\n')
        lines.extend(stderr_lines)
    
    for line in lines:
        # Parse different types of output
        if ';' in line and not line.startswith("Hello"):
            # This is a trace line with hash
            trace_lines.append(line)
            
            # Extract step number and hash from trace
            # Format: pc;reg0;reg1;...;hash
            parts = line.split(';')
            if len(parts) >= 14:  # Ensure we have hash at the end
                step_num = len(trace_lines) - 1
                step_hash = parts[-1].strip()  # Last field is the hash
                
                # Store checkpoints at intervals
                if step_num % checkpoint_interval == 0:
                    checkpoints.append((step_num, step_hash))
                
                # Update final hash
                final_hash = step_hash
                
        elif line.startswith("Halt"):
            # Extract payout from halt message
            # Format: "Halt(value, steps)"
            try:
                parts = line.strip()[5:-1].split(', ')
                payout = int(parts[0])
                total_steps = int(parts[1])
            except:
                pass
        elif "Hello world" in line:
            # Current ELF is hello world, extract any return value
            # The actual option settlement would return the payout
            pass
    
    # If we got trace lines, use that count as total steps
    if trace_lines and total_steps == 0:
        total_steps = len(trace_lines)
    
    # Add final checkpoint if not already included
    if checkpoints and checkpoints[-1][0] != total_steps - 1:
        checkpoints.append((total_steps - 1, final_hash))
    
    return BitVMXExecutionResult(
        payout=payout,
        total_steps=total_steps,
        final_hash=final_hash,
        trace_output=trace_lines,
        checkpoints=checkpoints
    )

def extract_checkpoints_for_challenge(
    result: BitVMXExecutionResult,
    arity: int = 4
) -> Dict:
    """
    Extract checkpoints optimized for n-ary search in challenge protocol
    
    Args:
        result: BitVMX execution result
        arity: Number of segments for n-ary search (default 4)
    
    Returns:
        Dictionary with challenge protocol data
    """
    return {
        'total_steps': result.total_steps,
        'final_hash': result.final_hash,
        'checkpoints': [
            {
                'step': step,
                'hash': hash_value
            } for step, hash_value in result.checkpoints
        ],
        'max_challenge_rounds': calculate_max_rounds(result.total_steps, arity),
        'arity': arity
    }

def calculate_max_rounds(total_steps: int, arity: int) -> int:
    """Calculate maximum rounds needed for n-ary search"""
    import math
    if total_steps <= 0:
        return 0
    # logₐ(n) where a is arity
    return math.ceil(math.log(total_steps) / math.log(arity))

def create_option_settlement_proof(
    option_type: int,
    strike_price: int,
    spot_price: int,
    quantity: int
) -> Dict:
    """
    Create a complete option settlement proof using BitVMX
    
    Args:
        option_type: 0=Call, 1=Put
        strike_price: Strike price in cents
        spot_price: Spot price in cents
        quantity: Quantity * 100
    
    Returns:
        Complete proof with BitVMX hash chain
    """
    
    # Prepare input
    input_data = struct.pack('<IIII',
        option_type,
        strike_price,
        spot_price,
        quantity
    )
    input_hex = input_data.hex()
    
    print(f"Running BitVMX option settlement...")
    print(f"  Option Type: {'Call' if option_type == 0 else 'Put'}")
    print(f"  Strike: ${strike_price / 100:.2f}")
    print(f"  Spot: ${spot_price / 100:.2f}")
    print(f"  Quantity: {quantity / 100:.2f}")
    
    # Run BitVMX with its native hash chain
    result = run_bitvmx_with_hash_chain(
        "execution_files/option_settlement.elf",
        input_hex
    )
    
    if result is None:
        return {'error': 'BitVMX execution failed'}
    
    print(f"\nExecution complete:")
    print(f"  Steps: {result.total_steps}")
    print(f"  Final Hash: {result.final_hash}")
    print(f"  Payout: ${result.payout / 100:.2f}")
    
    # Create proof structure
    proof = {
        'option_input': {
            'option_type': option_type,
            'strike_price': strike_price,
            'spot_price': spot_price,
            'quantity': quantity
        },
        'bitvmx_execution': {
            'total_steps': result.total_steps,
            'final_hash': result.final_hash,
            'payout_cents': result.payout
        },
        'challenge_data': extract_checkpoints_for_challenge(result),
        'metadata': {
            'elf_hash': compute_elf_hash("execution_files/option_settlement.elf"),
            'protocol_version': '1.0'
        }
    }
    
    return proof

def compute_elf_hash(elf_path: str) -> str:
    """Compute SHA256 hash of the ELF binary"""
    import hashlib
    with open(elf_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def main():
    """Example usage"""
    
    # Example 1: Call option ITM
    print("=== Example 1: Call Option (In The Money) ===")
    proof1 = create_option_settlement_proof(
        option_type=0,  # Call
        strike_price=5000000,  # $50,000
        spot_price=5200000,    # $52,000
        quantity=100           # 1.0 BTC
    )
    
    # Save proof
    with open('bitvmx_settlement_proof.json', 'w') as f:
        json.dump(proof1, f, indent=2)
    
    print(f"\nProof saved to bitvmx_settlement_proof.json")
    
    # Example 2: Put option OTM
    print("\n=== Example 2: Put Option (Out of The Money) ===")
    proof2 = create_option_settlement_proof(
        option_type=1,  # Put
        strike_price=5000000,  # $50,000
        spot_price=5200000,    # $52,000
        quantity=100           # 1.0 BTC
    )
    
    print(f"\nPut option payout: ${proof2['bitvmx_execution']['payout_cents'] / 100:.2f}")

if __name__ == "__main__":
    main()