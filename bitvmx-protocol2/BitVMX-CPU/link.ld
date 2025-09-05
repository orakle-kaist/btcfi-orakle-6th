SECTIONS
{
    . = 0x1000;
    .text : { *(.text.entry) *(.text) }
    
    . = 0xAA000000;
    .input : { *(.input) }
    
    . = 0xE0000000;
    .stack : { . = . + 0x1000; }
    
    . = 0xF0000000;
    .output : { *(.output) }
}