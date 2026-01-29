# ibsim Control Panel

A simple web utility that wraps the [InfiniBand Simulator (`ibsim`)](https://github.com/linux-rdma/ibsim) to make it easier to learn and use.

`ibsim` is an InfiniBand fabric simulator that emulates the behavior of InfiniBand networks by intercepting Management Datagram (MAD) traffic. It allows you to run standard InfiniBand diagnostic tools (like `ibnetdiscover`, `smpquery`, and `OpenSM`) against a simulated topology without needing physical hardware. It works by using a preloaded library (`libumad2sim.so`) to redirect calls from the user-space MAD library to the simulator process.

This tool provides a GUI to design network topologies, manage simulations, run Open Subnet Managers (OpenSM), and execute diagnostic commands in a simulated environment.

> **⚠️ Security Warning**: This application is **not production-grade** and contains inherent security flaws. It allows execution of shell commands and does not implement robust authentication or authorization. It is intended strictly for **educational and learning purposes** in a local, isolated environment.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)

## Features

-   **Topology Editor**:
    -   **Visual Editor**: Interactive drag-and-drop interface powered by Cytoscape.js to create Switches and HCAs (Host Channel Adapters).
    -   **Text Editor**: Direct access to the underlying `.net` topology file format.
    -   **Auto-Layout**: Automatically arrange nodes for better visibility.
-   **Simulation Management**:
    -   Start/Stop the `ibsim` process.
    -   Real-time log streaming for the simulation.
-   **OpenSM Control**:
    -   Run multiple instances of OpenSM (Primary and Secondary).
    -   Select specific HCAs to run OpenSM on.
    -   Edit `opensm.conf` directly from the UI.
-   **Interactive Terminal**:
    -   Embedded web terminal (`ttyd`) with pre-configured environment variables (`LD_PRELOAD` for `umad2sim`).
    -   Run standard InfiniBand diagnostic commands (`ibnetdiscover`, `iblinkinfo`, `smpquery`, etc.) against the running simulation.
-   **Modern UI**: Built with [NiceGUI](https://nicegui.io/) for a responsive and dark-themed experience.

## Prerequisites

This project relies on `ibsim`, which is a Linux-only tool. For this reason, **Docker** or **Podman** is the strongly recommended way to run this application, especially on macOS or Windows, as they provide the necessary Linux environment (via a VM).

-   **Docker** and **Docker Compose** (or **Podman** and **Podman Compose**) (Recommended method)
-   Or Python 3.12+ and required system libraries (`opensm`, `infiniband-diags`, `libibumad`, etc.) if running on a native Linux system.

## Getting Started

### Using Docker Compose (or Podman Compose)

The easiest way to run the project is using Docker Compose (or Podman Compose), which handles all dependencies including the compiled `ibsim` tool. This ensures the application runs in a compatible Linux environment regardless of your host OS.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/zbrooks422/ibsim_control_panel.git
    cd ibsim_control_panel
    ```

2.  **Start the container:**
    ```bash
    # Using Docker
    docker compose up --build

    # Using Podman
    podman compose up --build
    ```

3.  **Access the application:**
    Open your browser and navigate to `http://localhost:8080`.

## Usage Guide

### 1. Designing a Topology
Navigate to the **Topology Editor** tab.
-   **Add Nodes**: Use the "Add Switch" or "Add Node" (HCA) buttons.
-   **Connect**: Click "Connect Mode", then click a source node followed by a target node.
-   **Properties**: Click any node or edge to edit its properties (Name, Port Count, Source/Target Ports) in the right-hand panel.
-   **Save**: Click "Save" to write the changes to the `net` file.

### 2. Running a Simulation
Navigate to the **Control** tab.
1.  **Start ibsim**: Click "Start" in the Simulation card. Wait for the status to turn green.
2.  **Start OpenSM**: Select an HCA from the dropdown (e.g., `sm-primary` or any HCA you added) and click "Start".
    -   *Note: You need at least one running OpenSM to bring the subnet up.*

### 3. Troubleshooting & Diagnostics
Navigate to the **Troubleshoot** tab.
1.  Click **Launch Terminal**.
2.  The terminal will launch **ibsim-connect**. Select an HCA from the list to connect to the simulation.
3.  Once connected, you can run commands like:
    ```bash
    # View the fabric topology
    ibnetdiscover

    # Check link status
    iblinkinfo
    
    # Trace a route between lids
    ibtracert 1 2
    ```
    *Note: The terminal environment is automatically configured to talk to the simulator.*

## Project Structure

-   `src/ibsim_control_panel/`: Application source code.
    -   `app.py`: Main application logic and UI layout.
    -   `topology.py`: Parsers for converting between `.net` files and visual formats.
    -   `defaults/`: Default configuration files.
    -   `static/`: Static assets (CSS/JS).
-   `src/ibsim_shell/`: Shell integration module.
    -   `cli.py`: Interactive CLI for connecting to HCAs.
-   `config/`: Local configuration directory (created on startup).
    -   `net`: The active topology file.
    -   `opensm.conf`: Configuration file for OpenSM.
-   `tests/`: Unit and integration tests.
-   `Dockerfile`: Environment definition.
-   `docker-compose.yml`: Container orchestration configuration.

## Development

To install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
python -m pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
