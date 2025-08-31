/* BitVMX RISC-V32 Linker Script - Fixed Memory Map */
OUTPUT_FORMAT("elf32-littleriscv", "elf32-littleriscv", "elf32-littleriscv")
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    text     (rx)  : ORIGIN = 0x80000000, LENGTH = 0x10000000  /* Code */
    data     (rw)  : ORIGIN = 0x90000000, LENGTH = 0x10000000  /* Initialized data */
    bss      (rw)  : ORIGIN = 0xA0000000, LENGTH = 0x0A000000  /* Uninitialized data */
    input    (rw)  : ORIGIN = 0xAA000000, LENGTH = 0x01000000  /* Input from emulator */
    rodata   (r)   : ORIGIN = 0xB0000000, LENGTH = 0x10000000  /* Read-only data */
    stack    (rw)  : ORIGIN = 0xE0000000, LENGTH = 0x00800000  /* Stack: 0xE0000000-0xE0800000 */
    registers (rw) : ORIGIN = 0xF0000000, LENGTH = 0x10000000  /* CPU registers - DO NOT TOUCH */
}

SECTIONS
{
    /* Code section */
    .text : {
        *(.text.entry)
        *(.text)
        *(.text.*)
    } > text

    /* Read-only data */
    .rodata : {
        *(.rodata)
        *(.rodata.*)
    } > rodata

    /* Initialized data */
    .data : {
        *(.data)
        *(.data.*)
    } > data

    /* Uninitialized data */
    .bss : {
        __bss_start = .;
        *(.bss)
        *(.bss.*)
        *(COMMON)
        __bss_end = .;
    } > bss

    /* Input section for emulator */
    .input : {
        *(.input)
        *(.input.*)
    } > input

    /* Stack section */
    .stack : {
        . = ALIGN(16);
        __stack_start = .;
        . = . + 0x7ff000;  /* ~8MB stack */
        __stack_top = .;
    } > stack

    /* Registers - managed by emulator */
    .registers : {
        *(.registers)
    } > registers

    /* Provide symbols for runtime */
    PROVIDE(__global_pointer$ = .);
    PROVIDE(__stack_pointer = __stack_top);
}