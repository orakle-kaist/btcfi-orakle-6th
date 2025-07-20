#!/bin/bash

# Build Option Verification Program for BitVMX
# This script compiles the Rust option verification program to RISC-V target for BitVMX execution

set -e

echo "Building option verification program for BitVMX..."

# Check if RISC-V target is installed
if ! rustup target list --installed | grep -q "riscv32imc-unknown-none-elf"; then
    echo "Installing RISC-V target..."
    rustup target add riscv32imc-unknown-none-elf
fi

# Navigate to option verification program directory
cd option_verification_program

# Build the option verification program for RISC-V
echo "Compiling option verification program to RISC-V..."
cargo build --release --target riscv32imc-unknown-none-elf

# Copy the binary to BitVMX emulator directory for processing
VERIFICATION_BIN="target/riscv32imc-unknown-none-elf/release/option-verification-program"
BITVMX_DIR="../BitVMX-CPU/emulator"

if [ -f "$VERIFICATION_BIN" ]; then
    echo "Option verification program compiled successfully: $VERIFICATION_BIN"
    
    # Copy to BitVMX emulator directory if it exists
    if [ -d "$BITVMX_DIR" ]; then
        cp "$VERIFICATION_BIN" "$BITVMX_DIR/"
        echo "Option verification program copied to BitVMX emulator directory"
    else
        echo "Warning: BitVMX emulator directory not found at $BITVMX_DIR"
    fi
else
    echo "Error: Failed to compile option verification program"
    exit 1
fi

echo "Option verification program build complete!"
echo "Binary location: $PWD/$VERIFICATION_BIN"
echo "File size: $(wc -c < "$VERIFICATION_BIN") bytes"

# Generate program hash using BitVMX emulator if available
if [ -d "$BITVMX_DIR" ] && [ -f "$BITVMX_DIR/Cargo.toml" ]; then
    echo "Generating program commitment hash..."
    cd "$BITVMX_DIR"
    
    if cargo run --bin emulator -- --program ../option_verification_program/$VERIFICATION_BIN --commitment 2>/dev/null; then
        echo "Program commitment generated successfully"
    else
        echo "Warning: Could not generate program commitment (emulator may not be ready)"
    fi
fi

echo "Build script completed!"