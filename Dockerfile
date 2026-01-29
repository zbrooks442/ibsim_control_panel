FROM ubuntu:24.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Update and install packages
# opensm: InfiniBand subnet manager
# infiniband-diags: Diagnostic utilities
# ibutils: Additional utilities
# iproute2: For network interface management
# build-essential, git, libibumad-dev, libibmad-dev: For building ibsim
# python3, python3-pip: For the web interface
RUN apt-get update && apt-get install -y \
    opensm \
    infiniband-diags \
    ibutils \
    iproute2 \
    build-essential \
    git \
    libibumad-dev \
    libibmad-dev \
    python3 \
    python3-pip \
    tmux \
    ttyd \
    nano \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Build and install ibsim from source
WORKDIR /tmp
RUN git clone https://github.com/linux-rdma/ibsim.git && \
    cd ibsim && \
    make && \
    make install && \
    cd / && \
    rm -rf /tmp/ibsim

# Set configuration directory
ENV IBSIM_CONFIG_DIR=/config
RUN mkdir -p /config

# Set a working directory
WORKDIR /workspace

# Copy local files to the container
COPY . /workspace

# Install the package
# Using --break-system-packages because Ubuntu 24.04 enforces PEP 668
RUN pip3 install --no-cache-dir . --break-system-packages

# Expose the web interface port and terminal port
EXPOSE 8080 7681

# Default command: run the installed package entry point
CMD ["python3", "-m", "ibsim_control_panel"]
