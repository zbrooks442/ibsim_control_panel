"""Main application module for IBSim Control Panel."""

import os
import signal
import subprocess
import threading
import asyncio
import shutil
from pathlib import Path
from importlib import resources
from nicegui import ui, app

from .constants import NET_FILE, OPENSM_CONF, CONFIG_DIR
from .topology import (
    read_net_file,
    parse_net_to_mermaid,
    parse_net_to_dict,
    dict_to_net_file,
    topology_to_cytoscape_json,
)

# Global state for processes
ibsim_process = None
opensm_processes = {}
terminal_process = None
term_iframe = None
terminal_launched = False

# Status tracking for UI updates
ibsim_status_badge = None
opensm_primary_status_badge = None
opensm_secondary_status_badge = None

# Global visualization component
mermaid_view = None

# Global visual editor components
visual_editor_container = None
current_topology = None
text_editor_ref = None

# Global log storage
ibsim_logs = []
opensm_primary_logs = []
opensm_secondary_logs = []

# Global property panel state
selected_element_data = {"type": None, "data": None}


def init_cytoscape_editor():
    """Initialize Cytoscape editor with full functionality."""
    net_content = read_net_file()
    topology = parse_net_to_dict(net_content)
    elements_json = topology_to_cytoscape_json(topology)

    return f"""
    <script>
        window.initialTopology = {elements_json};
    </script>
    <script src="/static/js/cytoscape_init.js"></script>
    """


async def save_from_visual_editor():  # noqa: C901
    """Save topology from visual editor to file and sync with text editor."""
    try:
        print("[DEBUG] save_from_visual_editor() called")

        # Check if cyActions exists first
        exists = await ui.run_javascript('typeof window.cyActions !== "undefined"', timeout=2)

        print(f"[DEBUG] window.cyActions exists: {exists}")

        if not exists:
            ui.notify("Visual editor not initialized. Please wait a moment and try again.", type="warning")
            return

        # Get topology from JavaScript
        topology_json = await ui.run_javascript("JSON.stringify(window.cyActions.getTopology())", timeout=10)

        if topology_json:
            import json

            topology = json.loads(topology_json)

            print(f"[DEBUG] Saving topology with {len(topology['nodes'])} nodes and {len(topology['edges'])} edges")

            # Validate topology structure
            if "nodes" not in topology or "edges" not in topology:
                raise ValueError("Invalid topology structure: missing 'nodes' or 'edges'")

            # Validate each node has required fields
            for node in topology["nodes"]:
                if "id" not in node or "type" not in node or "ports" not in node:
                    raise ValueError(f"Invalid node structure: {node}")

            # Validate each edge has required fields
            for edge in topology["edges"]:
                if not all(key in edge for key in ["source", "target", "sourcePort", "targetPort"]):
                    raise ValueError(f"Invalid edge structure: {edge}")

            # Convert to net file format
            net_content = dict_to_net_file(topology)

            print(f"[DEBUG] Generated net file content ({len(net_content)} chars)")

            # Save to file
            with open(NET_FILE, "w") as f:
                f.write(net_content)

            # Update text editor if it exists
            if text_editor_ref:
                text_editor_ref.value = net_content

            # Update mermaid view
            if mermaid_view:
                mermaid_view.content = parse_net_to_mermaid(net_content)

            ui.notify("Topology saved successfully!", type="positive")
        else:
            ui.notify("Failed to get topology from editor", type="negative")
    except Exception as e:
        print(f"[ERROR] Failed to save topology: {e}")
        import traceback

        traceback.print_exc()
        ui.notify(f"Error saving topology: {str(e)}", type="negative")


async def reload_from_text_editor():
    """Reload topology from text editor into visual editor."""
    try:
        # Check if cyActions exists first
        exists = await ui.run_javascript('typeof window.cyActions !== "undefined"', timeout=2)

        if not exists:
            ui.notify("Visual editor not initialized. Please wait a moment and try again.", type="warning")
            return

        # Read current net file
        net_content = read_net_file()

        # Parse to dict
        topology = parse_net_to_dict(net_content)

        # Convert to Cytoscape format
        elements_json = topology_to_cytoscape_json(topology)

        # Reload in Cytoscape
        await ui.run_javascript(f"window.cyActions.loadTopology({elements_json})", timeout=10)

        ui.notify("Topology reloaded from text editor", type="positive")
    except Exception as e:
        ui.notify(f"Failed to reload topology: {e}", type="negative")


def save_net_file(content):
    """Save network topology content to file."""
    with open(NET_FILE, "w") as f:
        f.write(content)
    ui.notify("Network topology saved!", type="positive")

    # Update visualization if it exists
    if mermaid_view:
        mermaid_view.content = parse_net_to_mermaid(content)


def get_hca_names():
    """Get list of HCA names from the current topology."""
    try:
        content = read_net_file()
        topology = parse_net_to_dict(content)
        return [n["id"] for n in topology["nodes"] if n["type"] == "Hca"]
    except Exception:
        return []


def read_opensm_conf():
    """Read OpenSM configuration from file."""
    if os.path.exists(OPENSM_CONF):
        with open(OPENSM_CONF, "r") as f:
            return f.read()
    return ""


def save_opensm_conf(content):
    """Save OpenSM configuration to file."""
    with open(OPENSM_CONF, "w") as f:
        f.write(content)
    ui.notify("OpenSM configuration saved!", type="positive")


async def start_ibsim(log_element, start_btn, stop_btn):
    """Start the ibsim process."""
    global ibsim_process, ibsim_status_badge
    if ibsim_process and ibsim_process.poll() is None:
        ui.notify("ibsim is already running", type="warning")
        return

    # Use absolute path for NET_FILE to avoid any ambiguity
    abs_net_file = os.path.abspath(NET_FILE)
    if not os.path.exists(abs_net_file):
        ui.notify(f"Network file not found at {abs_net_file}", type="negative")
        return

    # Disable buttons during operation
    start_btn.props("loading")

    cmd = ["ibsim", "-s", abs_net_file]
    try:
        # Start ibsim
        # We use preexec_fn=os.setsid to easily kill the process group later if needed
        ibsim_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, preexec_fn=os.setsid
        )
        ui.notify("ibsim started successfully", type="positive")

        # Update status badge
        if ibsim_status_badge:
            ibsim_status_badge.set_text("Running")
            ibsim_status_badge.props("color=positive")

        start_btn.props(remove="loading")

        # Background thread to read output
        def read_output():
            for line in iter(ibsim_process.stdout.readline, ""):
                if line:
                    stripped_line = line.strip()
                    ibsim_logs.append(stripped_line)
                    log_element.push(stripped_line)
            ibsim_process.stdout.close()

        threading.Thread(target=read_output, daemon=True).start()

    except Exception as e:
        ui.notify(f"Failed to start ibsim: {e}", type="negative")
        log_element.push(f"[Error] {e}")
        start_btn.props(remove="loading")


async def stop_ibsim(stop_btn):
    """Stop the ibsim process."""
    global ibsim_process, ibsim_status_badge
    if ibsim_process:
        stop_btn.props("loading")
        try:
            os.killpg(os.getpgid(ibsim_process.pid), signal.SIGTERM)
            ibsim_process = None
            ui.notify("ibsim stopped successfully", type="positive")

            # Update status badge
            if ibsim_status_badge:
                ibsim_status_badge.set_text("Stopped")
                ibsim_status_badge.props("color=grey")

            stop_btn.props(remove="loading")
        except Exception as e:
            ui.notify(f"Error stopping ibsim: {e}", type="negative")
            stop_btn.props(remove="loading")
    else:
        ui.notify("ibsim is not running", type="warning")


async def start_opensm(log_element, hca="sm-primary", start_btn=None, stop_btn=None):  # noqa: C901
    """Start an OpenSM process for a specific HCA."""
    global opensm_processes, opensm_primary_status_badge, opensm_secondary_status_badge
    if hca in opensm_processes and opensm_processes[hca].poll() is None:
        ui.notify(f"opensm ({hca}) is already running", type="warning")
        return

    if start_btn:
        start_btn.props("loading")

    # Environment variables for OpenSM
    env = os.environ.copy()
    env["LD_PRELOAD"] = "/usr/lib/umad2sim/libumad2sim.so"
    env["SIM_HOST"] = hca

    cmd = ["opensm"]
    if os.path.exists(OPENSM_CONF):
        cmd.extend(["-F", OPENSM_CONF])

    try:
        process = subprocess.Popen(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, preexec_fn=os.setsid
        )
        opensm_processes[hca] = process
        ui.notify(f"opensm ({hca}) started successfully", type="positive")

        # Update status badge
        if hca == "sm-primary" and opensm_primary_status_badge:
            opensm_primary_status_badge.set_text("Running")
            opensm_primary_status_badge.props("color=positive")
        elif hca == "sm-secondary" and opensm_secondary_status_badge:
            opensm_secondary_status_badge.set_text("Running")
            opensm_secondary_status_badge.props("color=positive")

        if start_btn:
            start_btn.props(remove="loading")

        def read_output():
            for line in iter(process.stdout.readline, ""):
                if line:
                    stripped_line = line.strip()
                    log_line = f"[{hca}] {stripped_line}"
                    if hca == "sm-primary":
                        opensm_primary_logs.append(log_line)
                    elif hca == "sm-secondary":
                        opensm_secondary_logs.append(log_line)
                    log_element.push(log_line)
            process.stdout.close()

        threading.Thread(target=read_output, daemon=True).start()

    except Exception as e:
        ui.notify(f"Failed to start opensm ({hca}): {e}", type="negative")
        log_element.push(f"[Error] {e}")
        if start_btn:
            start_btn.props(remove="loading")


async def stop_opensm(hca="sm-primary", stop_btn=None):
    """Stop an OpenSM process."""
    global opensm_processes, opensm_primary_status_badge, opensm_secondary_status_badge
    if hca in opensm_processes and opensm_processes[hca]:
        if stop_btn:
            stop_btn.props("loading")
        try:
            os.killpg(os.getpgid(opensm_processes[hca].pid), signal.SIGTERM)
            del opensm_processes[hca]
            ui.notify(f"opensm ({hca}) stopped successfully", type="positive")

            # Update status badge
            if hca == "sm-primary" and opensm_primary_status_badge:
                opensm_primary_status_badge.set_text("Stopped")
                opensm_primary_status_badge.props("color=grey")
            elif hca == "sm-secondary" and opensm_secondary_status_badge:
                opensm_secondary_status_badge.set_text("Stopped")
                opensm_secondary_status_badge.props("color=grey")

            if stop_btn:
                stop_btn.props(remove="loading")
        except Exception as e:
            ui.notify(f"Error stopping opensm ({hca}): {e}", type="negative")
            if stop_btn:
                stop_btn.props(remove="loading")
    else:
        ui.notify(f"opensm ({hca}) is not running", type="warning")


async def _kill_existing_terminal():
    """Kill any existing terminal processes."""
    global terminal_process
    if terminal_process:
        try:
            os.killpg(os.getpgid(terminal_process.pid), signal.SIGTERM)
            terminal_process = None
        except Exception:
            pass

    # Force kill any lingering ttyd processes to avoid port conflicts
    try:
        subprocess.run(["pkill", "-f", "ttyd"], check=False)
        await asyncio.sleep(0.2)  # Wait for cleanup
    except Exception:
        pass


async def _wait_for_terminal_port(process, timeout=5.0):
    """Wait for the terminal port to be ready."""
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        if process.poll() is not None:
            return False  # Process died

        try:
            # Try to connect to the port
            reader, writer = await asyncio.open_connection("localhost", 7681)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, ConnectionRefusedError):
            await asyncio.sleep(0.1)
    return False


async def launch_terminal(launch_btn, reset_btn, stop_btn, empty_state_container, iframe_container):
    """Launch the web terminal."""
    global terminal_process, term_iframe, terminal_launched

    launch_btn.props("loading")
    reset_btn.props("loading")

    await _kill_existing_terminal()

    # Check if library exists
    lib_path = "/usr/lib/umad2sim/libumad2sim.so"
    if not os.path.exists(lib_path):
        ui.notify(f"ERROR: {lib_path} not found!", type="negative")
        launch_btn.props(remove="loading")
        reset_btn.props(remove="loading")
        return

    # Start new ttyd process
    env = os.environ.copy()

    # Use ibsim-connect directly for better UX
    cmd = ["ttyd", "-p", "7681", "-W", "-i", "0.0.0.0", "ibsim-connect"]

    # We must ensure environment variables are passed
    env["LD_PRELOAD"] = lib_path
    # User will set SIM_HOST manually

    try:
        terminal_process = subprocess.Popen(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid
        )

        # Wait for port to be ready (robust check)
        port_ready = await _wait_for_terminal_port(terminal_process)

        # Check if it crashed
        if terminal_process.poll() is not None:
            err = terminal_process.stderr.read().decode()
            ui.notify(f"ttyd failed to start: {err}", type="negative")
            launch_btn.props(remove="loading")
            reset_btn.props(remove="loading")
            return

        if not port_ready:
            ui.notify("Timeout waiting for terminal to start", type="negative")
            launch_btn.props(remove="loading")
            reset_btn.props(remove="loading")
            return

        ui.notify("Terminal launched successfully on port 7681", type="positive")

        # Hide empty state and show iframe
        terminal_launched = True
        empty_state_container.set_visibility(False)
        iframe_container.set_visibility(True)

        # Update buttons
        launch_btn.set_visibility(False)
        reset_btn.set_visibility(True)
        stop_btn.set_visibility(True)

        # Refresh iframe source to force reload
        # We append a timestamp to bust cache
        import time

        timestamp = time.time()

        new_content = f'<iframe src="http://localhost:7681/?t={timestamp}" width="100%" height="600px" style="border: 1px solid #475569; border-radius: 8px; background: #0f172a;"></iframe>'
        # Update the content property directly
        if term_iframe:
            term_iframe.content = new_content

        # Check connection script with page reload on failure
        ui.run_javascript("""
            setTimeout(async function() {
                try {
                    await fetch('http://localhost:7681', { mode: 'no-cors' });
                    console.log('Terminal connection verified');
                } catch (e) {
                    console.error('Terminal connection failed:', e);
                    // Add a visible notification before reloading
                    const notification = document.createElement('div');
                    notification.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#f44336;color:white;padding:16px;border-radius:4px;z-index:9999;box-shadow:0 4px 6px rgba(0,0,0,0.1);font-family:sans-serif;';
                    notification.textContent = 'Connection failed. Auto-refreshing page to fix...';
                    document.body.appendChild(notification);

                    setTimeout(() => window.location.reload(), 1500);
                }
            }, 1000);
        """)

        launch_btn.props(remove="loading")
        reset_btn.props(remove="loading")

    except Exception as e:
        ui.notify(f"Failed to launch terminal: {e}", type="negative")
        launch_btn.props(remove="loading")
        reset_btn.props(remove="loading")


async def stop_terminal_session(launch_btn, reset_btn, stop_btn, empty_state_container, iframe_container):
    """Stop the terminal session."""
    global terminal_process, term_iframe, terminal_launched

    stop_btn.props("loading")

    if terminal_process:
        try:
            os.killpg(os.getpgid(terminal_process.pid), signal.SIGTERM)
            terminal_process = None
        except Exception:
            pass

    # Kill ttyd
    try:
        subprocess.run(["pkill", "-f", "ttyd"], check=False)
    except Exception:
        pass

    terminal_launched = False

    # Update UI
    empty_state_container.set_visibility(True)
    iframe_container.set_visibility(False)

    launch_btn.set_visibility(True)
    reset_btn.set_visibility(False)
    stop_btn.set_visibility(False)

    stop_btn.props(remove="loading")
    ui.notify("Terminal session stopped", type="positive")


@ui.page("/")
def index():  # noqa: C901
    """Main page entry point."""
    # Set default tab in storage if not present
    if "active_tab" not in app.storage.user:
        app.storage.user["active_tab"] = "Control"

    # Dark theme colors
    ui.colors(
        primary="#0891b2",
        secondary="#64748b",
        accent="#00d9ff",
        positive="#10b981",
        negative="#ef4444",
        warning="#f59e0b",
        dark="#1a1f2e",
        dark_page="#0f172a",
    )

    # Add custom dark theme styling and Cytoscape
    ui.add_head_html("""
        <link rel="stylesheet" href="/static/css/styles.css">
        <!-- Cytoscape.js core library -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
    """)

    # Modern header with gradient and status
    with ui.header().classes("px-6 py-4"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("settings_ethernet", size="lg").classes("text-cyan-400")
                ui.label("InfiniBand Simulator").classes("text-2xl font-bold text-slate-100")
            # Status indicator could go here if needed

    # Modern tabs with icons
    with ui.tabs().classes("w-full bg-slate-900 shadow-lg").bind_value(app.storage.user, "active_tab") as tabs:
        control_tab = ui.tab("Control", icon="play_circle")
        visual_editor_tab = ui.tab("Topology Editor", icon="draw")
        _troubleshoot_tab = ui.tab("Troubleshoot", icon="bug_report")

    with ui.tab_panels(tabs, value=app.storage.user["active_tab"]).classes("w-full p-6"):

        # Control Panel with modern cards
        with ui.tab_panel(control_tab):

            # OpenSM Configuration (Expandable)
            with ui.expansion("OpenSM Configuration", icon="settings").classes(
                "w-full bg-slate-800 border-slate-700 mb-4"
            ):
                with ui.card().classes("w-full bg-slate-900/50 p-4"):
                    ui.label("Edit opensm.conf directly").classes("text-sm text-slate-400 mb-2")

                    opensm_editor = (
                        ui.textarea(value=read_opensm_conf())
                        .classes(
                            "w-full font-mono text-sm bg-black/30 text-slate-100 border border-slate-600 rounded p-3"
                        )
                        .props("rows=10")
                    )

                    with ui.row().classes("gap-2 mt-2"):
                        ui.button(
                            "Save Configuration", icon="save", on_click=lambda: save_opensm_conf(opensm_editor.value)
                        ).props("color=positive outline")
                        ui.button(
                            "Reload from Disk",
                            icon="refresh",
                            on_click=lambda: opensm_editor.set_value(read_opensm_conf()),
                        ).props("color=warning outline")

            # Control cards - responsive grid
            with ui.row().classes("w-full gap-4 flex-wrap lg:flex-nowrap items-stretch"):
                # ibsim card
                with ui.card().classes("flex-1 min-w-[280px] bg-slate-800 border-slate-700 shadow-xl p-6"):
                    with ui.row().classes("items-center justify-between w-full mb-4"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("memory", size="md").classes("text-cyan-400")
                            ui.label("Simulation").classes("text-xl font-semibold text-slate-100")
                        global ibsim_status_badge
                        ibsim_status_badge = ui.badge("Stopped", color="grey").classes("text-sm")

                    ui.label("ibsim").classes("text-sm text-slate-400 mb-4")

                    with ui.row().classes("gap-2 w-full"):
                        ibsim_start_btn = ui.button("Start", icon="play_arrow").props("flat color=positive outline")
                        ibsim_stop_btn = ui.button("Stop", icon="stop").props("flat color=negative outline")

                        # Wire up buttons with proper parameters
                        ibsim_start_btn.on(
                            "click", lambda: start_ibsim(ibsim_log_view, ibsim_start_btn, ibsim_stop_btn)
                        )
                        ibsim_stop_btn.on("click", lambda: stop_ibsim(ibsim_stop_btn))

                # Primary SM card
                with ui.card().classes("flex-1 min-w-[280px] bg-slate-800 border-slate-700 shadow-xl p-6"):
                    with ui.row().classes("items-center justify-between w-full mb-4"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("hub", size="md").classes("text-emerald-400")
                            ui.label("Primary SM").classes("text-xl font-semibold text-slate-100")
                        global opensm_primary_status_badge
                        opensm_primary_status_badge = ui.badge("Stopped", color="grey").classes("text-sm")

                    # HCA Selection
                    hca_list = get_hca_names()
                    primary_default = "sm-primary" if "sm-primary" in hca_list else None
                    primary_hca_select = (
                        ui.select(options=hca_list, label="Select HCA", value=primary_default)
                        .classes("w-full mb-4 text-slate-100")
                        .props(
                            'outlined popup-content-class="bg-slate-800 text-slate-100" input-class="text-slate-100" label-color="slate-300"'
                        )
                    )

                    with ui.row().classes("gap-2 w-full"):
                        primary_start_btn = ui.button("Start", icon="play_arrow").props("flat color=positive outline")
                        primary_stop_btn = ui.button("Stop", icon="stop").props("flat color=negative outline")

                        async def start_primary_sm():
                            if not primary_hca_select.value:
                                ui.notify("Please select an HCA first", type="warning")
                                return
                            await start_opensm(
                                opensm_primary_log_view, primary_hca_select.value, primary_start_btn, primary_stop_btn
                            )

                        async def stop_primary_sm():
                            if not primary_hca_select.value:
                                return
                            await stop_opensm(primary_hca_select.value, primary_stop_btn)

                        primary_start_btn.on("click", start_primary_sm)
                        primary_stop_btn.on("click", stop_primary_sm)

                # Secondary SM card
                with ui.card().classes("flex-1 min-w-[280px] bg-slate-800 border-slate-700 shadow-xl p-6"):
                    with ui.row().classes("items-center justify-between w-full mb-4"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("hub", size="md").classes("text-purple-400")
                            ui.label("Secondary SM").classes("text-xl font-semibold text-slate-100")
                        global opensm_secondary_status_badge
                        opensm_secondary_status_badge = ui.badge("Stopped", color="grey").classes("text-sm")

                    # HCA Selection
                    secondary_default = "sm-secondary" if "sm-secondary" in hca_list else None
                    secondary_hca_select = (
                        ui.select(options=hca_list, label="Select HCA", value=secondary_default)
                        .classes("w-full mb-4 text-slate-100")
                        .props(
                            'outlined popup-content-class="bg-slate-800 text-slate-100" input-class="text-slate-100" label-color="slate-300"'
                        )
                    )

                    with ui.row().classes("gap-2 w-full"):
                        secondary_start_btn = ui.button("Start", icon="play_arrow").props("flat color=positive outline")
                        secondary_stop_btn = ui.button("Stop", icon="stop").props("flat color=negative outline")

                        async def start_secondary_sm():
                            if not secondary_hca_select.value:
                                ui.notify("Please select an HCA first", type="warning")
                                return
                            await start_opensm(
                                opensm_secondary_log_view,
                                secondary_hca_select.value,
                                secondary_start_btn,
                                secondary_stop_btn,
                            )

                        async def stop_secondary_sm():
                            if not secondary_hca_select.value:
                                return
                            await stop_opensm(secondary_hca_select.value, secondary_stop_btn)

                        secondary_start_btn.on("click", start_secondary_sm)
                        secondary_stop_btn.on("click", stop_secondary_sm)

            ui.separator().classes("my-6 bg-slate-700")

            # Log viewers with terminal styling - responsive
            with ui.row().classes("w-full gap-4 flex-wrap lg:flex-nowrap"):
                # ibsim logs
                with ui.card().classes("flex-1 min-w-[300px] bg-slate-900 border-slate-700 p-4"):
                    with ui.row().classes("items-center justify-between w-full mb-3"):
                        ui.label("ibsim Logs").classes("text-lg font-bold text-cyan-400")
                        with ui.row().classes("gap-1"):
                            ui.button(icon="clear_all", on_click=lambda: ibsim_log_view.clear()).props(
                                "flat dense size=sm"
                            ).classes("text-slate-400").tooltip("Clear logs")
                    ibsim_log_view = ui.log(max_lines=1000).classes(
                        "w-full h-96 bg-black/50 p-3 rounded border border-slate-700 text-sm font-mono"
                    )
                    # Pre-fill logs if exist (for page reload)
                    for line in ibsim_logs:
                        ibsim_log_view.push(line)

                # Primary SM logs
                with ui.card().classes("flex-1 min-w-[300px] bg-slate-900 border-slate-700 p-4"):
                    with ui.row().classes("items-center justify-between w-full mb-3"):
                        ui.label("Primary SM Logs").classes("text-lg font-bold text-emerald-400")
                        with ui.row().classes("gap-1"):
                            ui.button(icon="clear_all", on_click=lambda: opensm_primary_log_view.clear()).props(
                                "flat dense size=sm"
                            ).classes("text-slate-400").tooltip("Clear logs")
                    opensm_primary_log_view = ui.log(max_lines=1000).classes(
                        "w-full h-96 bg-black/50 p-3 rounded border border-slate-700 text-sm font-mono"
                    )
                    for line in opensm_primary_logs:
                        opensm_primary_log_view.push(line)

                # Secondary SM logs
                with ui.card().classes("flex-1 min-w-[300px] bg-slate-900 border-slate-700 p-4"):
                    with ui.row().classes("items-center justify-between w-full mb-3"):
                        ui.label("Secondary SM Logs").classes("text-lg font-bold text-purple-400")
                        with ui.row().classes("gap-1"):
                            ui.button(icon="clear_all", on_click=lambda: opensm_secondary_log_view.clear()).props(
                                "flat dense size=sm"
                            ).classes("text-slate-400").tooltip("Clear logs")
                    opensm_secondary_log_view = ui.log(max_lines=1000).classes(
                        "w-full h-96 bg-black/50 p-3 rounded border border-slate-700 text-sm font-mono"
                    )
                    for line in opensm_secondary_logs:
                        opensm_secondary_log_view.push(line)

        # Visual Editor Panel
        with ui.tab_panel(visual_editor_tab):
            # Add initialization script that will run when tab becomes visible
            ui.add_body_html(init_cytoscape_editor())

            # Text Topology Editor (Expandable)
            with ui.expansion("Text Topology Editor", icon="edit_note").classes(
                "w-full bg-slate-800 border-slate-700 mb-4"
            ):
                with ui.card().classes("w-full bg-slate-900/50 p-4"):
                    ui.label("Edit net file directly").classes("text-sm text-slate-400 mb-2")
                    global text_editor_ref
                    # Initialize with current file content
                    text_editor = (
                        ui.textarea(value=read_net_file())
                        .classes(
                            "w-full font-mono text-sm bg-black/30 text-slate-100 border border-slate-600 rounded p-3"
                        )
                        .props("rows=20")
                    )
                    text_editor_ref = text_editor

                    async def save_and_reload_topology():
                        save_net_file(text_editor.value)
                        await reload_from_text_editor()

                    with ui.row().classes("gap-2 mt-2"):
                        ui.button("Save & Update Visual", icon="save", on_click=save_and_reload_topology).props(
                            "color=positive outline"
                        )
                        ui.button(
                            "Reload from Disk", icon="refresh", on_click=lambda: text_editor.set_value(read_net_file())
                        ).props("color=warning outline")

            with ui.row().classes("w-full h-full gap-4"):
                # Main editor area (left side)
                with ui.column().classes("flex-1"):
                    # Top toolbar
                    with ui.card().classes("w-full bg-slate-800 border-slate-700 p-4 mb-4"):
                        with ui.row().classes("items-center gap-2 flex-wrap"):
                            ui.label("Tools").classes("text-sm font-bold text-slate-300 mr-2")

                            def add_switch_handler():
                                ui.notify("Click anywhere on the canvas to place a new switch", type="info")
                                ui.run_javascript("window.cyActions && window.cyActions.addSwitch()")

                            def add_hca_handler():
                                ui.notify("Click anywhere on the canvas to place a new HCA", type="info")
                                ui.run_javascript("window.cyActions && window.cyActions.addHca()")

                            def connect_mode_handler():
                                ui.notify("Connection mode: Click source node, then target node", type="info")
                                ui.run_javascript("window.cyActions && window.cyActions.toggleConnectMode()")

                            ui.button("Add Switch", icon="add_box", on_click=add_switch_handler).props(
                                "flat color=purple outline size=sm"
                            )
                            ui.button("Add Node", icon="computer", on_click=add_hca_handler).props(
                                "flat color=cyan outline size=sm"
                            )
                            ui.separator().props("vertical").classes("mx-2")
                            ui.button("Connect Mode", icon="timeline", on_click=connect_mode_handler).props(
                                "flat color=primary outline size=sm"
                            )
                            ui.separator().props("vertical").classes("mx-2")

                            def delete_selected_handler():
                                ui.run_javascript("""
                                    var selected = window.cy.$(':selected');
                                    if (selected.length > 0) {
                                        if (confirm('Delete selected ' + selected.length + ' element(s)?')) {
                                            selected.remove();
                                            window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                                            window.dispatchEvent(new CustomEvent('cy-deselect'));
                                        }
                                    } else {
                                        // Try to use the state if cy selection is empty (fallback)
                                        if (window.cyState && window.cyState.selectedElement) {
                                            var ele = window.cyState.selectedElement.element;
                                            if (confirm('Delete selected element?')) {
                                                ele.remove();
                                                window.cyState.selectedElement = null;
                                                window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                                                window.dispatchEvent(new CustomEvent('cy-deselect'));
                                            }
                                        }
                                    }
                                """)

                            ui.button("Delete", icon="delete", on_click=delete_selected_handler).props(
                                "flat color=negative outline size=sm"
                            )
                            ui.separator().props("vertical").classes("mx-2")

                            ui.button(
                                "Auto-Layout",
                                icon="account_tree",
                                on_click=lambda: ui.run_javascript("window.cyActions && window.cyActions.autoLayout()"),
                            ).props("flat color=positive outline size=sm")
                            (
                                ui.button(
                                    "",
                                    icon="undo",
                                    on_click=lambda: ui.run_javascript("window.cyActions && window.cyActions.undo()"),
                                )
                                .props("flat dense size=sm")
                                .tooltip("Undo (not available)")
                            )
                            (
                                ui.button(
                                    "",
                                    icon="redo",
                                    on_click=lambda: ui.run_javascript("window.cyActions && window.cyActions.redo()"),
                                )
                                .props("flat dense size=sm")
                                .tooltip("Redo (not available)")
                            )
                            ui.separator().props("vertical").classes("mx-2")
                            ui.button("Save", icon="save", on_click=save_from_visual_editor).props(
                                "flat color=positive outline size=sm"
                            )
                            ui.button("Reload from Text", icon="refresh", on_click=reload_from_text_editor).props(
                                "flat color=warning outline size=sm"
                            )
                            ui.separator().props("vertical").classes("mx-2")
                            (
                                ui.button(
                                    "Reinitialize",
                                    icon="restart_alt",
                                    on_click=lambda: ui.run_javascript(
                                        'if (window.reinitCytoscape) window.reinitCytoscape(); else console.error("[Cytoscape] Reinitialize function not available")'
                                    ),
                                )
                                .props("flat color=grey outline size=sm")
                                .tooltip("Manually reinitialize the editor if it fails to load")
                            )

                    # Help panel
                    with (
                        ui.expansion("Quick Help", icon="help")
                        .classes("w-full bg-slate-900/50 border-slate-700 mb-2")
                        .props("dense")
                    ):
                        with ui.column().classes("text-sm text-slate-300 gap-1 p-2"):
                            ui.label("🖱️ Add Switch/HCA: Click button, then click canvas to place").classes("text-xs")
                            ui.label("🔗 Connect Mode: Click button, then click source node → target node").classes(
                                "text-xs"
                            )
                            ui.label("✏️ Edit Properties: Click any node or edge to edit in right panel").classes(
                                "text-xs"
                            )
                            ui.label("🗑️ Delete: Select element, then use Delete button in properties panel").classes(
                                "text-xs"
                            )
                            ui.label("⌨️ Keyboard: Delete key, F (fit to screen)").classes("text-xs")

                    # Cytoscape canvas container
                    with ui.card().classes("w-full bg-slate-800 border-slate-700 p-4"):
                        with ui.row().classes("items-center justify-between w-full mb-2"):
                            ui.label("Network Topology Editor").classes("text-lg font-bold text-cyan-400")
                            ui.badge("Initializing...", color="warning").classes("text-sm")

                        global visual_editor_container
                        visual_editor_container = ui.html('<div id="cy"></div>', sanitize=False).classes("w-full")

                        # Update status when initialized
                        ui.timer(
                            1.0,
                            lambda: ui.run_javascript("""
                            if (typeof window.cy !== "undefined" && window.cy) {
                                document.querySelectorAll('.q-badge').forEach(b => {
                                    if (b.textContent.includes('Initializing')) {
                                        b.textContent = 'Ready';
                                        b.classList.remove('bg-warning');
                                        b.classList.add('bg-positive');
                                    }
                                });
                            }
                        """),
                            once=True,
                        )

                        # Zoom controls
                        with ui.row().classes("gap-2 mt-4"):
                            (
                                ui.button(
                                    "", icon="add", on_click=lambda: ui.run_javascript("window.cyActions.zoomIn()")
                                )
                                .props("flat dense size=sm")
                                .tooltip("Zoom In")
                            )
                            (
                                ui.button(
                                    "", icon="remove", on_click=lambda: ui.run_javascript("window.cyActions.zoomOut()")
                                )
                                .props("flat dense size=sm")
                                .tooltip("Zoom Out")
                            )
                            (
                                ui.button(
                                    "", icon="fit_screen", on_click=lambda: ui.run_javascript("window.cyActions.fit()")
                                )
                                .props("flat dense size=sm")
                                .tooltip("Fit to Screen")
                            )

                # Properties panel (right side)
                with ui.card().classes("w-80 bg-slate-800 border-slate-700 p-4"):
                    with ui.row().classes("w-full items-center justify-between mb-4"):
                        ui.label("Properties").classes("text-lg font-bold text-purple-400")
                        # Button created here, handler assigned later
                        edit_selected_btn = (
                            ui.button(icon="edit")
                            .props("flat dense size=sm color=primary")
                            .tooltip("Edit Selected Element")
                        )

                    # Selection status indicator
                    selection_status = ui.label("No selection").classes("text-xs text-slate-500 mb-2")

                    # Empty state
                    properties_empty = ui.column().classes("w-full items-center justify-center py-12")
                    with properties_empty:
                        ui.icon("info", size="lg").classes("text-slate-600 mb-2")
                        ui.label("Select a node or edge").classes("text-sm text-slate-400 text-center")
                        with ui.column().classes("items-center gap-1 mt-3"):
                            ui.label("1. Click on a node/edge in the graph").classes(
                                "text-xs text-slate-500 text-center"
                            )
                            ui.label("2. Click the edit button above").classes("text-xs text-slate-500 text-center")

                    # Node properties (hidden by default)
                    node_properties = ui.column().classes("w-full gap-3")
                    with node_properties:
                        ui.label("Node Properties").classes("text-md font-semibold text-slate-200 mb-2")
                        node_name_input = ui.input("Name").classes("w-full")
                        ui.label("Type: Switch").classes("text-sm text-slate-400")
                        node_ports_input = ui.number("Port Count", min=1, max=128, value=32).classes("w-full")
                        ui.separator().classes("my-2")

                        async def update_node_handler():
                            # Get values from NiceGUI components directly
                            new_name = node_name_input.value
                            new_ports = int(node_ports_input.value)

                            # Pass the values to JavaScript
                            result = await ui.run_javascript(
                                f"""
                                (function() {{
                                    var newName = {repr(new_name)};
                                    var newPorts = {new_ports};
                                    console.log('[Properties] Updating node with name:', newName, 'ports:', newPorts);

                                    if (!window.cyState || !window.cyState.selectedElement || window.cyState.selectedElement.type !== 'node') {{
                                        return {{ success: false, error: 'No node selected' }};
                                    }}

                                    var node = window.cyState.selectedElement.element;
                                    var oldId = node.id();

                                    try {{
                                        window.cyActions.updateNode(oldId, {{ label: newName, ports: newPorts }});
                                        console.log('[Properties] Node updated successfully from', oldId, 'to', newName);
                                        return {{ success: true }};
                                    }} catch(e) {{
                                        console.error('[Properties] Error updating node:', e);
                                        return {{ success: false, error: e.toString() }};
                                    }}
                                }})();
                            """,
                                timeout=5,
                            )

                            if result and result.get("success"):
                                ui.notify(f'Node updated to "{new_name}"', type="positive")
                            else:
                                error_msg = result.get("error", "Unknown error") if result else "No response"
                                ui.notify(f"Failed to update node: {error_msg}", type="negative")

                        def delete_node_handler():
                            ui.run_javascript("""
                                if (window.cyState && window.cyState.selectedElement && window.cyState.selectedElement.type === 'node') {
                                    var node = window.cyState.selectedElement.element;
                                    if (confirm('Delete node "' + node.id() + '" and all its connections?')) {
                                        window.cyActions.deleteNode(node.id());
                                    }
                                }
                            """)

                        (
                            ui.button("Update Node", icon="check", on_click=update_node_handler)
                            .props("color=positive outline")
                            .classes("w-full")
                        )
                        (
                            ui.button("Delete Node", icon="delete", on_click=delete_node_handler)
                            .props("color=negative outline")
                            .classes("w-full")
                        )
                    node_properties.set_visibility(False)

                    # Edge properties (hidden by default)
                    edge_properties = ui.column().classes("w-full gap-3")
                    with edge_properties:
                        ui.label("Edge Properties").classes("text-md font-semibold text-slate-200 mb-2")
                        edge_source_label = ui.label("Source: -").classes("text-sm text-slate-400")
                        edge_source_port_input = ui.number("Source Port", min=1, value=1).classes("w-full")
                        edge_target_label = ui.label("Target: -").classes("text-sm text-slate-400")
                        edge_target_port_input = ui.number("Target Port", min=1, value=1).classes("w-full")
                        ui.separator().classes("my-2")

                        def update_edge_handler():
                            ui.run_javascript("""
                                // Get all source/target port inputs and take the last ones (edge properties, not node properties)
                                var sourcePortInputs = document.querySelectorAll('input[aria-label="Source Port"]');
                                var targetPortInputs = document.querySelectorAll('input[aria-label="Target Port"]');
                                var sourcePortInput = sourcePortInputs[sourcePortInputs.length - 1];
                                var targetPortInput = targetPortInputs[targetPortInputs.length - 1];

                                var sourcePort = parseInt(sourcePortInput.value);
                                var targetPort = parseInt(targetPortInput.value);
                                console.log('[Properties] Updating edge with sourcePort:', sourcePort, 'targetPort:', targetPort);
                                if (window.cyState && window.cyState.selectedElement && window.cyState.selectedElement.type === 'edge') {
                                    var edge = window.cyState.selectedElement.element;
                                    window.cyActions.updateEdge(edge.id(), { sourcePort: sourcePort, targetPort: targetPort });
                                }
                            """)

                        def delete_edge_handler():
                            ui.run_javascript("""
                                if (window.cyState && window.cyState.selectedElement && window.cyState.selectedElement.type === 'edge') {
                                    var edge = window.cyState.selectedElement.element;
                                    if (confirm('Delete this connection?')) {
                                        window.cyActions.deleteEdge(edge.id());
                                    }
                                }
                            """)

                        (
                            ui.button("Update Connection", icon="check", on_click=update_edge_handler)
                            .props("color=positive outline")
                            .classes("w-full")
                        )
                        (
                            ui.button("Delete Connection", icon="delete", on_click=delete_edge_handler)
                            .props("color=negative outline")
                            .classes("w-full")
                        )
                    edge_properties.set_visibility(False)

                    # Logic to load properties into Python components
                    async def load_selected_properties():
                        # Fetch full data from JavaScript to Python
                        result = await ui.run_javascript(
                            """
                            (function() {
                                if (!window.cy) return { success: false, error: 'Editor not initialized' };

                                var selected = window.cy.$(':selected');
                                if (selected.length === 0) {
                                    return { success: false, error: 'No element selected' };
                                }

                                var element = selected[0];
                                if (element.isNode()) {
                                    return {
                                        success: true,
                                        type: 'node',
                                        id: element.id(),
                                        label: element.data('label'),
                                        ports: element.data('ports')
                                    };
                                } else if (element.isEdge()) {
                                    return {
                                        success: true,
                                        type: 'edge',
                                        id: element.id(),
                                        source: element.source().id(),
                                        target: element.target().id(),
                                        sourcePort: element.data('sourcePort'),
                                        targetPort: element.data('targetPort')
                                    };
                                }
                                return { success: false, error: 'Unknown element type' };
                            })();
                        """,
                            timeout=3,
                        )

                        if result and result.get("success"):
                            elem_type = result.get("type")

                            # Update Python state directly (Reliable)
                            if elem_type == "node":
                                properties_empty.set_visibility(False)
                                node_properties.set_visibility(True)
                                edge_properties.set_visibility(False)

                                node_name_input.value = result.get("label") or result.get("id")
                                node_ports_input.value = result.get("ports", 32)
                                selection_status.text = f"Selected: Node '{result.get('id')}'"

                            elif elem_type == "edge":
                                properties_empty.set_visibility(False)
                                node_properties.set_visibility(False)
                                edge_properties.set_visibility(True)

                                # Update specific edge inputs
                                edge_source_port_input.value = result.get("sourcePort", 1)
                                edge_target_port_input.value = result.get("targetPort", 1)
                                edge_source_label.text = f"Source: {result.get('source')}"
                                edge_target_label.text = f"Target: {result.get('target')}"

                                selection_status.text = (
                                    f"Selected: Edge {result.get('source')} <-> {result.get('target')}"
                                )

                            ui.notify(f'Loaded {elem_type}: {result.get("id")}', type="positive")
                        else:
                            error = result.get("error", "No element selected") if result else "No response"
                            ui.notify(f"{error}", type="warning")

                    # Wire up the button handler now that the function is defined
                    edit_selected_btn.on("click", load_selected_properties)

                    # Add JavaScript event listeners to update properties panel
                    # Store references for updating from JavaScript
                    ui.add_body_html("""
                    <script>
                    (function() {
                        // Helper to find panel containers by looking for specific text
                        function findPanelContainers() {
                            var allColumns = document.querySelectorAll('.q-column');
                            var emptyPanel, nodePanel, edgePanel;

                            for (var i = 0; i < allColumns.length; i++) {
                                var col = allColumns[i];
                                var text = col.textContent || '';

                                if (text.includes('Select a node or edge')) {
                                    emptyPanel = col;
                                } else if (text.includes('Node Properties') && !text.includes('Edge')) {
                                    nodePanel = col;
                                } else if (text.includes('Edge Properties')) {
                                    edgePanel = col;
                                }
                            }

                            return { emptyPanel: emptyPanel, nodePanel: nodePanel, edgePanel: edgePanel };
                        }

                        // Helper to properly update NiceGUI input values
                        function updateInputValue(input, newValue) {
                            if (!input) return;

                            // Set the value
                            input.value = newValue;

                            // Trigger multiple events to ensure NiceGUI picks up the change
                            var events = ['input', 'change', 'blur'];
                            events.forEach(function(eventName) {
                                var event = new Event(eventName, { bubbles: true, cancelable: true });
                                input.dispatchEvent(event);
                            });

                            // Also try to update the underlying Vue component if it exists
                            if (input.__vue__) {
                                input.__vue__.$emit('update:modelValue', newValue);
                            }
                        }

                        // Wait for properties panel elements to be ready
                        setTimeout(function() {
                            console.log('[Properties] Setting up event listeners');

                            // Listen for node selection
                            window.addEventListener('cy-node-selected', function(e) {
                                console.log('[Properties] Node selected event received:', e.detail);
                                var data = e.detail;
                                var panels = findPanelContainers();

                                // Show node panel, hide others
                                if (panels.emptyPanel) {
                                    panels.emptyPanel.style.display = 'none';
                                    console.log('[Properties] Hiding empty panel');
                                }
                                if (panels.nodePanel) {
                                    panels.nodePanel.style.display = 'flex';
                                    console.log('[Properties] Showing node panel');
                                }
                                if (panels.edgePanel) {
                                    panels.edgePanel.style.display = 'none';
                                    console.log('[Properties] Hiding edge panel');
                                }

                                // Update selection status indicator
                                var statusLabels = document.querySelectorAll('.q-label');
                                for (var i = 0; i < statusLabels.length; i++) {
                                    if (statusLabels[i].textContent.includes('No selection') ||
                                        statusLabels[i].textContent.includes('Selected:')) {
                                        statusLabels[i].textContent = 'Selected: ' + (data.type || 'Switch') + ' "' + (data.label || data.id) + '"';
                                        break;
                                    }
                                }

                                // Update input values using proper method
                                var nameInput = document.querySelector('input[aria-label="Name"]');
                                var portsInput = document.querySelector('input[aria-label="Port Count"]');

                                console.log('[Properties] Updating name input to:', data.label || data.id);
                                console.log('[Properties] Updating ports input to:', data.ports || 32);

                                updateInputValue(nameInput, data.label || data.id);
                                updateInputValue(portsInput, data.ports || 32);

                                console.log('[Properties] Node properties loaded successfully');
                            });

                            // Listen for edge selection
                            window.addEventListener('cy-edge-selected', function(e) {
                                console.log('[Properties] Edge selected event received:', e.detail);
                                var data = e.detail;
                                var panels = findPanelContainers();

                                // Show edge panel, hide others
                                if (panels.emptyPanel) {
                                    panels.emptyPanel.style.display = 'none';
                                    console.log('[Properties] Hiding empty panel');
                                }
                                if (panels.nodePanel) {
                                    panels.nodePanel.style.display = 'none';
                                    console.log('[Properties] Hiding node panel');
                                }
                                if (panels.edgePanel) {
                                    panels.edgePanel.style.display = 'flex';
                                    console.log('[Properties] Showing edge panel');
                                }

                                // Update selection status indicator
                                var statusLabels = document.querySelectorAll('.q-label');
                                for (var i = 0; i < statusLabels.length; i++) {
                                    if (statusLabels[i].textContent.includes('No selection') ||
                                        statusLabels[i].textContent.includes('Selected:')) {
                                        statusLabels[i].textContent = 'Selected: Connection ' + data.source + ' → ' + data.target;
                                        break;
                                    }
                                }

                                // Update input values
                                var sourcePortInputs = document.querySelectorAll('input[aria-label="Source Port"]');
                                var targetPortInputs = document.querySelectorAll('input[aria-label="Target Port"]');

                                // Get the edge property inputs (not node property inputs)
                                var sourcePortInput = sourcePortInputs[sourcePortInputs.length - 1];
                                var targetPortInput = targetPortInputs[targetPortInputs.length - 1];

                                console.log('[Properties] Updating source port to:', data.sourcePort);
                                console.log('[Properties] Updating target port to:', data.targetPort);

                                updateInputValue(sourcePortInput, data.sourcePort || 1);
                                updateInputValue(targetPortInput, data.targetPort || 1);

                                console.log('[Properties] Edge properties loaded successfully');
                            });

                            // Listen for deselection
                            window.addEventListener('cy-deselect', function(e) {
                                console.log('[Properties] Deselect event received');
                                var panels = findPanelContainers();

                                // Show empty panel, hide others
                                if (panels.emptyPanel) {
                                    panels.emptyPanel.style.display = 'flex';
                                    console.log('[Properties] Showing empty panel');
                                }
                                if (panels.nodePanel) {
                                    panels.nodePanel.style.display = 'none';
                                    console.log('[Properties] Hiding node panel');
                                }
                                if (panels.edgePanel) {
                                    panels.edgePanel.style.display = 'none';
                                    console.log('[Properties] Hiding edge panel');
                                }

                                // Reset selection status indicator
                                var statusLabels = document.querySelectorAll('.q-label');
                                for (var i = 0; i < statusLabels.length; i++) {
                                    if (statusLabels[i].textContent.includes('Selected:') ||
                                        statusLabels[i].textContent.includes('No selection')) {
                                        statusLabels[i].textContent = 'No selection';
                                        break;
                                    }
                                }
                            });

                            console.log('[Properties] Event listeners registered');
                        }, 500);
                    })();
                    </script>
                    """)

    # Troubleshooting Panel with modern styling - kept outside tab_panels to preserve iframe state
    with ui.column().classes("w-full p-6").bind_visibility_from(tabs, "value", lambda v: v == "Troubleshoot"):
        global term_iframe

        # Warning banner for missing simulation/SM
        with ui.card().classes(
            "w-full bg-warning/20 border-warning text-warning mb-4 items-center flex-row gap-4 p-4"
        ) as warning_banner:
            ui.icon("warning", size="md")
            with ui.column().classes("gap-0"):
                ui.label("Simulation or Subnet Manager not running").classes("font-bold")
                ui.label(
                    "Terminal commands may fail. Please start ibsim and at least one SM in the Control tab."
                ).classes("text-sm")

        # Function to check status and update banner
        def update_warning_banner():
            is_ibsim_running = ibsim_process is not None and ibsim_process.poll() is None
            is_any_sm_running = any(p is not None and p.poll() is None for p in opensm_processes.values())

            if not is_ibsim_running or not is_any_sm_running:
                warning_banner.set_visibility(True)
            else:
                warning_banner.set_visibility(False)

        # Update immediately and then every 2 seconds
        update_warning_banner()
        ui.timer(2.0, update_warning_banner)

        with ui.row().classes("items-center justify-between w-full mb-4"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("terminal", size="md").classes("text-cyan-400")
                ui.label("Interactive Terminal").classes("text-2xl font-bold").style("color: #f1f5f9 !important;")

            with ui.row().classes("gap-2"):
                launch_btn = ui.button("Launch Terminal", icon="rocket_launch").props("color=positive outline")
                reset_btn = ui.button("Reset Terminal", icon="refresh").props("color=warning outline")
                stop_btn = ui.button("Stop Terminal", icon="stop").props("color=negative outline")

                # Initially hidden
                reset_btn.set_visibility(False)
                stop_btn.set_visibility(False)

        ui.separator().classes("my-4 bg-slate-700")

        # Collapsible instructions
        with ui.expansion("Command Reference & Setup", icon="help_outline").classes(
            "w-full bg-slate-800 border border-slate-700 text-slate-100 mb-4"
        ):
            with ui.card().classes("bg-slate-900/50 border-0 p-4"):
                ui.markdown("""
### Interactive Shell

The terminal will automatically launch **ibsim-connect** which will:
<br>
1. Scan the current topology
<br>
2. Ask you to select an HCA (Node) to connect to
<br>
3. Configure the environment (`SIM_HOST` and `LD_PRELOAD`)
<br>
4. Launch a shell for you to run commands
<br>

### Supported Commands

- `ibnetdiscover` - **Best for viewing full topology**. Shows all nodes and links.
- `iblinkinfo` - Shows link status for all ports (up/down/speed).
- `ibswitches` - List all switches.
- `ibhosts` - List all hosts (HCAs).
- `smpquery nodeinfo <LID>` - Query node info (e.g., `smpquery nodeinfo 1`).
- `ibroute` - Show switch routing tables (e.g., `ibroute <SwitchLID>`).
- `ibtracert <SourceLID> <DestLID>` - Trace path between nodes.
- `saquery` - Query Subnet Administration data (requires OpenSM).

**Note:** Traffic generation tools like `ibping` are not supported by ibsim as it only simulates management packets (MADs).
""").classes("text-slate-300 text-sm")

        ui.separator().classes("my-4 bg-slate-700")

        # Empty state (shown before terminal is launched)
        with ui.card().classes(
            "w-full bg-slate-800/50 border-slate-700 p-12 text-center shadow-xl"
        ) as empty_state_container:
            ui.icon("terminal", size="4rem").classes("text-slate-600 mb-4")
            ui.label("No Terminal Session Active").classes("text-xl font-semibold text-slate-300 mb-2")
            ui.label('Click "Launch Terminal" above to start an interactive shell session').classes(
                "text-sm text-slate-400 mb-4"
            )
            with ui.row().classes("justify-center gap-4 mt-6"):
                with ui.column().classes("items-center"):
                    ui.icon("settings", size="lg").classes("text-cyan-400 mb-2")
                    ui.label("Auto-Configuration").classes("text-xs text-slate-400")
                    ui.label("Selects HCA").classes("text-xs font-mono text-slate-500")
                with ui.column().classes("items-center"):
                    ui.icon("code", size="lg").classes("text-purple-400 mb-2")
                    ui.label("IB Commands").classes("text-xs text-slate-400")
                    ui.label("Ready to use").classes("text-xs font-mono text-slate-500")

        # Terminal iframe container (hidden until launched)
        with ui.column().classes("w-full") as iframe_container:
            term_iframe = ui.html(
                '<iframe src="http://localhost:7681" width="100%" height="600px" style="border: 1px solid #475569; border-radius: 8px; background: #0f172a;"></iframe>',
                sanitize=False,
            ).classes("w-full shadow-xl")

        iframe_container.set_visibility(False)

        # Wire up the buttons with the containers
        launch_btn.on(
            "click", lambda: launch_terminal(launch_btn, reset_btn, stop_btn, empty_state_container, iframe_container)
        )
        reset_btn.on(
            "click", lambda: launch_terminal(launch_btn, reset_btn, stop_btn, empty_state_container, iframe_container)
        )
        stop_btn.on(
            "click",
            lambda: stop_terminal_session(launch_btn, reset_btn, stop_btn, empty_state_container, iframe_container),
        )


def initialize_files():
    """Initialize configuration files from defaults if they don't exist in CWD."""
    from . import defaults

    # Ensure config directory exists
    if CONFIG_DIR and CONFIG_DIR != ".":
        os.makedirs(CONFIG_DIR, exist_ok=True)

    files_to_check = {NET_FILE: "net", OPENSM_CONF: "opensm.conf"}

    for filename, resource_name in files_to_check.items():
        # Handle case where file exists as a directory (e.g. from bad volume mount)
        if os.path.exists(filename) and os.path.isdir(filename):
            print(f"[Init] Removing directory {filename} to replace with file")
            shutil.rmtree(filename)

        if not os.path.exists(filename):
            print(f"[Init] {filename} not found, copying from defaults...")
            try:
                source = resources.files(defaults).joinpath(resource_name)
                # as_file ensures it's a real file path even if in a zip
                with resources.as_file(source) as src_path:
                    shutil.copy(src_path, filename)
                print(f"[Init] Successfully created {filename}")
            except Exception as e:
                print(f"[Init] Failed to copy {filename}: {e}")
        else:
            print(f"[Init] Found existing {filename}")


def cleanup_processes():
    """Clean up any running processes on shutdown."""
    global ibsim_process, terminal_process
    print("Cleaning up processes...")

    # Kill ibsim
    if ibsim_process:
        try:
            os.killpg(os.getpgid(ibsim_process.pid), signal.SIGTERM)
        except Exception:
            pass

    # Kill terminal
    if terminal_process:
        try:
            os.killpg(os.getpgid(terminal_process.pid), signal.SIGTERM)
        except Exception:
            pass

    # Kill opensm processes
    for _hca, process in opensm_processes.items():
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception:
            pass

    # Force kill any ttyd
    try:
        subprocess.run(["pkill", "-f", "ttyd"], check=False)
    except Exception:
        pass


def main():
    """Entry point for the application."""
    initialize_files()
    app.on_shutdown(cleanup_processes)
    app.add_static_files("/static", str(Path(__file__).parent / "static"))
    ui.run(title="IB Simulator", host="0.0.0.0", port=8080, storage_secret="ibsimulator_secret", reload=False)
