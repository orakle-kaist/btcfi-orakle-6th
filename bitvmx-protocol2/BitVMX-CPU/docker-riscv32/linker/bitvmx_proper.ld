ENTRY(_start)

SECTIONS
{
    .text 0x80000000: ALIGN(4) {
        *(.text)
        *(.text.*)
        . = ALIGN(4);
    }

    .data 0x90000000 : ALIGN(4) {
        *(.data)
        *(.data.*)
        . = ALIGN(4);
    }

    .bss 0xA0000000 : ALIGN(4) {
        *(.bss)
        *(.bss.*)
        *(COMMON)
        . = ALIGN(4);
    } 

    /* Stack section - MUST have size */
    .stack 0xE0000000 : ALIGN(4) {
        . = . + 0x800000;  /* 8MB stack space */
        . = ALIGN(4);
    }

    .input 0xAA000000 : ALIGN(4) {
        *(.input)
        *(.input.*)
        . = ALIGN(4);
    }
    
    .registers 0xF0000000 : ALIGN(4) {
        *(.registers)
        . = ALIGN(4);
    }
    
    .rodata 0xB0000000 : ALIGN(4) {
        *(.rodata)
        *(.rodata.*) 
        . = ALIGN(4);
    }
}