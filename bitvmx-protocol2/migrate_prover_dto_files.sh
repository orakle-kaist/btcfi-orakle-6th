#!/bin/bash

# Migrate all bitvmx_protocol_verifier_dto.json files to bitvmx_protocol_prover_dto.json

echo "Starting migration of ProverDTO files..."
echo "==========================================="

PROVER_FILES_DIR="/Users/parkgeonwoo/oracle_vm/btcfi-orakle-6th/bitvmx-protocol2/prover_files"
count=0
success=0
failed=0

# Find all verifier_dto.json files
for old_file in $(find "$PROVER_FILES_DIR" -name "bitvmx_protocol_verifier_dto.json"); do
    count=$((count + 1))
    dir=$(dirname "$old_file")
    new_file="$dir/bitvmx_protocol_prover_dto.json"
    
    echo "[$count] Processing: $old_file"
    
    # Check if new file already exists
    if [ -f "$new_file" ]; then
        echo "  ⚠️  Target file already exists: $new_file"
        echo "  ⚠️  Skipping to avoid overwrite"
        failed=$((failed + 1))
    else
        # Rename the file
        mv "$old_file" "$new_file"
        if [ $? -eq 0 ]; then
            echo "  ✅ Migrated to: $new_file"
            success=$((success + 1))
        else
            echo "  ❌ Failed to migrate"
            failed=$((failed + 1))
        fi
    fi
    echo ""
done

echo "==========================================="
echo "Migration Complete!"
echo "Total files found: $count"
echo "Successfully migrated: $success"
echo "Failed/Skipped: $failed"
echo "==========================================="

# Verify migration
echo ""
echo "Verification:"
remaining=$(find "$PROVER_FILES_DIR" -name "bitvmx_protocol_verifier_dto.json" | wc -l)
migrated=$(find "$PROVER_FILES_DIR" -name "bitvmx_protocol_prover_dto.json" | wc -l)

echo "Remaining old files (verifier_dto): $remaining"
echo "New files (prover_dto): $migrated"