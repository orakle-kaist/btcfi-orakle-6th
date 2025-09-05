ENTRY(_start)

SECTIONS
{

    .text 0x80000000 : ALIGN(4) {
        KEEP(*(.init))      /* crt0.S startup code */
        *(.text .text.*)
        . = ALIGN(4);
    }

    .data 0x90000000 : ALIGN(4) {
        __global_pointer$ = . + 0x800;
        *(.data .data.*)
        . = ALIGN(4);
    }

    .bss 0xA0000000 : ALIGN(4) {
        __bss_start = .;
        *(.bss .bss.* COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } 

    .stack 0xE0000000 :  ALIGN(4) {
        *(.stack)
        . = . + 0x1000;  /* Reserve 4KB for stack */
        . = ALIGN(4);
        _stack_top = .;   /* Stack top at section end */
    }

    .input 0xAA000000 :  ALIGN(4) {
        *(.input)
        . = ALIGN(4);
    }
    
    .output 0xAB000000 : ALIGN(4) {
        *(.output)
        . = ALIGN(4);
    }
    
    .noinit 0xE0800000 (NOLOAD) : ALIGN(4) {
        *(.noinit)
        . = ALIGN(4);
    }
    
    .registers 0xF0000000 : ALIGN(4) {
        *(.registers)
        . = ALIGN(4);
    }
    
    .rodata 0xB0000000 : ALIGN(4) {
        *(.rodata .rodata.*)
        . = ALIGN(4);
    }
}
