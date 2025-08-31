/* Ultra minimal linker script for BitVMX */
ENTRY(_start)

MEMORY {
  RAM (rwx) : ORIGIN = 0x80000000, LENGTH = 256K
}

SECTIONS
{
  . = 0x80000000;
  
  .text : {
    *(.text.entry)
    *(.text*)
    *(.rodata*)
  } > RAM

  . = ALIGN(16);
  .data : {
    *(.data*)
  } > RAM

  . = ALIGN(16);
  .input : {
    KEEP(*(.input))
  } > RAM

  . = ALIGN(16);  
  .output : {
    KEEP(*(.output))
  } > RAM

  . = ALIGN(16);
  .bss : {
    *(.bss*)
  } > RAM

  . = ALIGN(16);
  .noinit (NOLOAD) : {
    *(.noinit*)
  } > RAM

  /DISCARD/ : {
    *(.comment*)
    *(.eh_frame*)
    *(.debug*)
  }
}