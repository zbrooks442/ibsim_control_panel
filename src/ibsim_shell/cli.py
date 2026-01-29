"""CLI tool to connect to IBSim HCAs."""

import os
import sys
import questionary
from ibsim_control_panel.topology import read_net_file, parse_net_to_dict


def main():
    """Interactive CLI to select HCA and start a shell."""
    # 1. Read net file
    try:
        content = read_net_file()
    except Exception as e:
        print(f"Error reading net file: {e}")
        sys.exit(1)

    if not content:
        print("Net file is empty or not found.")
        sys.exit(1)

    # 2. Parse HCAs
    try:
        topology = parse_net_to_dict(content)
        hcas = [n["id"] for n in topology["nodes"] if n["type"] == "Hca"]
    except Exception as e:
        print(f"Error parsing topology: {e}")
        sys.exit(1)

    if not hcas:
        print("No HCAs found in topology.")
        sys.exit(1)

    # 3. Interactive Selection
    try:
        selected_hca = questionary.select(
            "Select an HCA to connect to:",
            choices=sorted(hcas),
            use_indicator=True,
            style=questionary.Style(
                [
                    ("qmark", "fg:#0891b2 bold"),  # primary color
                    ("question", "bold"),
                    ("answer", "fg:#10b981 bold"),  # positive color
                    ("pointer", "fg:#00d9ff bold"),  # accent color
                    ("highlighted", "fg:#00d9ff bold"),  # accent color
                    ("selected", "fg:#10b981 bold"),  # positive color
                ]
            ),
        ).ask()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)

    if not selected_hca:
        print("No HCA selected.")
        sys.exit(0)

    # 4. Launch Shell
    print(f"Starting shell for {selected_hca}...")
    print(f"Exporting SIM_HOST={selected_hca}")

    env = os.environ.copy()
    env["SIM_HOST"] = selected_hca

    # Ensure LD_PRELOAD is set if not already
    lib_path = "/usr/lib/umad2sim/libumad2sim.so"
    if os.path.exists(lib_path) and "LD_PRELOAD" not in env:
        print(f"Exporting LD_PRELOAD={lib_path}")
        env["LD_PRELOAD"] = lib_path

    # Get preferred shell
    shell = env.get("SHELL", "/bin/bash")

    # Replace current process with the shell
    try:
        os.execlpe(shell, shell, env)
    except Exception as e:
        print(f"Failed to start shell: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
