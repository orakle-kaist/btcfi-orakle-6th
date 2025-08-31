FROM riscv32:latest

WORKDIR /

RUN apt-get update && \
    apt-get install -y clang git build-essential vim && \
    apt-get clean

RUN cd /src && \ 
    git clone -v --recursive https://github.com/FairgateLabs/bitvmx-zk-verifier --branch custom_flags

RUN cp -r /riscv32/riscv32-unknown-elf/include/* /src/bitvmx-zk-verifier/mcl/include/  




