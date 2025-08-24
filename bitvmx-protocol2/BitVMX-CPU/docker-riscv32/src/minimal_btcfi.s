# Minimal BTCFi in RISC-V Assembly - Target: <50 steps
.section .text
.global _start

_start:
    # Load input address
    li a0, 0xAA000000      # Input base
    li a1, 0xAA001000      # Output base
    
    # Load values
    lw t0, 0(a0)           # spot price
    lw t1, 4(a0)           # strike price  
    lw t2, 8(a0)           # option type (0=call, 1=put)
    
    # Check option type
    beqz t2, check_call    # if type == 0, check call
    
check_put:
    # Put: ITM if strike > spot
    bgt t1, t0, itm        # if strike > spot, ITM
    j otm
    
check_call:
    # Call: ITM if spot > strike
    bgt t0, t1, itm        # if spot > strike, ITM
    
otm:
    li t3, 0               # Result = 0 (OTM)
    j write_result
    
itm:
    li t3, 1               # Result = 1 (ITM)
    
write_result:
    sw t3, 0(a1)           # Write result
    
halt:
    j halt                 # Infinite loop for BitVMX