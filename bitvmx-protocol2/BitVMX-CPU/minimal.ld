ENTRY(_start)

SECTIONS
{
    . = 0x0;
    .text : {
        *(.text)
        *(.text.*)
    }
    
    . = 0xE0000000;
    .stack : {
        *(.stack)
        . = . + 0x1000;
    }
    
    . = 0xAA000000;
    .input : {
        *(.input)
    }
    
    . = 0xF0000000;
    .registers : {
        *(.registers)
    }
}