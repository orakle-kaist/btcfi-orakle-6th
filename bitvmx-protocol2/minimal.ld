/* Minimal linker script */
ENTRY(_start)

MEMORY {
  RAM (wx) : ORIGIN = 0x80000000, LENGTH = 256K
}

SECTIONS
{
  . = 0x80000000;
  
  .text : {
    *(.text.entry)
    *(.text*)
  } > RAM

  .data : { 
    *(.data*) 
  } > RAM
  
  .input : {
    KEEP(*(.input))
  } > RAM

  .bss : {
    *(.bss*)
  } > RAM

  . = 0x80040000;
  _stack_top = .;
}