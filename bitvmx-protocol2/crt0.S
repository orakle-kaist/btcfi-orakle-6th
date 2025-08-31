/* crt0.S - RISC-V32 startup code */
    .section .init
    .globl _start
_start:
    /* Set stack pointer from linker symbol */
    la   sp, _stack_top

    /* Set global pointer for optimizations */
    .option push
    .option norelax
    la   gp, __global_pointer$
    .option pop

    /* Clear BSS section */
    la   t0, __bss_start
    la   t1, __bss_end
    li   t2, 0
1:
    bgeu t0, t1, 2f
    sw   t2, 0(t0)
    addi t0, t0, 4
    j    1b
2:
    /* Call main */
    call main

    /* Infinite loop on exit */
3:
    j 3b