FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential git sudo vim \
    autoconf automake curl python3 libmpc-dev libmpfr-dev libgmp-dev gawk \
    bison flex texinfo gperf libtool patchutils bc zlib1g-dev libexpat-dev \
    && apt-get clean

RUN mkdir /src && \
  cd /src && \
  git clone https://github.com/riscv/riscv-gnu-toolchain --branch 2024.09.03

RUN cd /src/riscv-gnu-toolchain/ && \
  ./configure --prefix=/riscv32 --with-arch=rv32im --with-abi=ilp32 && \
  make -j 8 

#get some files to compile multiplication and division for riscv32
RUN cd /src && curl -LJO https://github.com/gcc-mirror/gcc/raw/master/libgcc/config/epiphany/mulsi3.c \
            && curl -LJO https://github.com/gcc-mirror/gcc/raw/master/libgcc/config/riscv/riscv-asm.h \ 
            && curl -LJO https://github.com/gcc-mirror/gcc/raw/master/libgcc/config/riscv/div.S 


# Define a build argument (default to false)
ARG INSTALL_QEMU=false

# Skip QEMU installation for now (dependency issues)
RUN apt-get update && apt-get install -y dos2unix && apt-get clean

ENV PATH=/riscv32/bin:$PATH

ENV CC=riscv32-unknown-elf-gcc
ENV CXX=riscv32-unknown-elf-c++
ENV CPP=riscv32-unknown-elf-cpp
ENV AS=riscv32-unknown-elf-as
ENV LD=riscv32-unknown-elf-ld
ENV AR=riscv32-unknown-elf-ar
ENV DUMP=riscv32-unknown-elf-objdump
ENV RANLIB=riscv32-unknown-elf-ranlib
ENV HOST=riscv32-unknown-elf
ENV QEMU=qemu-riscv32

WORKDIR /data

# Default command
CMD ["/bin/bash"]