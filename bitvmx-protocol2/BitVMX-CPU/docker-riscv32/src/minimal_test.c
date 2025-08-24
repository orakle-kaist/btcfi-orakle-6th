// Minimal test program with .input and .output sections
#include <stdint.h>

// Create .input section with proper alignment
__attribute__((section(".input"), used, aligned(16)))
unsigned char input_buffer[256] = {0};

// Create .output section with proper alignment
__attribute__((section(".output"), used, aligned(16)))
unsigned char output_buffer[256] = {0};

int main() {
    // Read first 4 bytes from input
    uint32_t value = *(uint32_t*)input_buffer;
    
    // Simple computation: add 10
    uint32_t result = value + 10;
    
    // Write result to output
    *(uint32_t*)output_buffer = result;
    
    return 0;
}