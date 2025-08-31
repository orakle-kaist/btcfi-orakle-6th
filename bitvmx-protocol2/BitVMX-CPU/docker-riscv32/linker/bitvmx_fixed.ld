ENTRY(_start)

MEMORY {
  ROM (rx) : ORIGIN = 0xF0000000, LENGTH = 8M
  RAM (rw) : ORIGIN = 0xE0000000, LENGTH = 8M
}

SECTIONS {
  .text : {
    KEEP(*(.text.entry*))      /* Preserve _start entry point */
    *(.text .text.*)
    *(.rodata .rodata.*)
  } > ROM

  .data : {
    *(.data .data.*)
  } > RAM AT > ROM

  .bss (NOLOAD) : {
    __bss_start = .;
    *(.bss .bss.*)
    *(COMMON)
    __bss_end = .;
  } > RAM

  .noinit (NOLOAD) : {
    *(.noinit .noinit.*)
  } > RAM

  /* Input/output buffers in RAM */
  .input 0xAA000000 : {
    KEEP(*(.input .input.*))
  }

  .output 0xAB000000 : {
    KEEP(*(.output .output.*))
  }

  /* Global pointer for small data */
  PROVIDE(__global_pointer$ = . + 0x800);
  
  /* Stack top at end of RAM with margin */
  __stack_top = ORIGIN(RAM) + LENGTH(RAM) - 64;
}