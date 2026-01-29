"""Topology parsing and conversion utilities."""

import os
import json
from .constants import NET_FILE


def read_net_file():
    """Read the network topology file."""
    if os.path.exists(NET_FILE):
        with open(NET_FILE, "r") as f:
            return f.read()
    return ""


def parse_net_to_mermaid(net_content):
    """Parse net content to Mermaid graph format."""
    graph = "graph LR;\n"
    current_node = None

    # Simple parsing:
    # Switch/Hca lines define nodes
    # [port] "remote"[port] lines define edges

    # We use a set to track added edges to avoid duplicates (A->B and B->A)
    # Storing tuple (node1, node2) where node1 < node2
    added_edges = set()

    for line in net_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()

        # Check for node definition
        if parts[0] in ["Switch", "Hca"]:
            # Format: Type ports "Name"
            # We need to extract name from quotes
            node_name = line.split('"')[1]
            current_node = node_name

            # Add node style
            if parts[0] == "Switch":
                graph += f'    {current_node}["{current_node}"]:::switch;\n'
            else:
                graph += f'    {current_node}["{current_node}"]:::hca;\n'

        elif line.startswith("[") and current_node:
            # Format: [local] "remote"[remote]
            try:
                # Extract remote node name
                remote_node = line.split('"')[1]

                # Check for duplicate edge
                n1, n2 = sorted((current_node, remote_node))
                if (n1, n2) not in added_edges:
                    graph += f"    {current_node} --- {remote_node};\n"
                    added_edges.add((n1, n2))
            except Exception:
                pass

    # Add styles for dark theme
    graph += "    classDef switch fill:#7c3aed,stroke:#a78bfa,stroke-width:2px,color:#f1f5f9;\n"
    graph += "    classDef hca fill:#0891b2,stroke:#06b6d4,stroke-width:2px,color:#f1f5f9;\n"

    return graph


def parse_net_to_dict(net_content):  # noqa: C901
    """Parse net file into a dictionary structure for visual editor."""
    topology = {"nodes": [], "edges": []}

    current_node = None
    node_ports = {}  # Track used ports per node

    for line in net_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()

        # Check for node definition: Switch/Hca ports "Name"
        if len(parts) >= 3 and parts[0] in ["Switch", "Hca"]:
            try:
                node_type = parts[0]
                port_count = int(parts[1])
                # Extract name from quotes
                node_name = line.split('"')[1]

                topology["nodes"].append({"id": node_name, "type": node_type, "ports": port_count})

                current_node = node_name
                node_ports[node_name] = {}
            except (IndexError, ValueError):
                continue

        # Check for edge definition: [port] "remote"[port]
        elif line.startswith("[") and current_node:
            try:
                # Extract port numbers and remote node name
                # Format: [1] "remote-node"[2]
                parts = line.split('"')
                if len(parts) >= 3:
                    source_port_str = parts[0].strip()
                    remote_name = parts[1]
                    target_port_str = parts[2].strip()

                    # Extract port numbers from brackets
                    source_port = int(source_port_str.strip("[]"))
                    target_port = int(target_port_str.strip("[]"))

                    # Add edge (avoid duplicates by checking if reverse already exists)
                    edge_id = f"{current_node}:{source_port}-{remote_name}:{target_port}"
                    # reverse_id = f"{remote_name}:{target_port}-{current_node}:{source_port}"

                    # Check if this edge already exists
                    existing = False
                    for edge in topology["edges"]:
                        if (
                            edge["source"] == current_node
                            and edge["target"] == remote_name
                            and edge["sourcePort"] == source_port
                            and edge["targetPort"] == target_port
                        ):
                            existing = True
                            break
                        if (
                            edge["source"] == remote_name
                            and edge["target"] == current_node
                            and edge["sourcePort"] == target_port
                            and edge["targetPort"] == source_port
                        ):
                            existing = True
                            break

                    if not existing:
                        topology["edges"].append(
                            {
                                "id": edge_id,
                                "source": current_node,
                                "target": remote_name,
                                "sourcePort": source_port,
                                "targetPort": target_port,
                            }
                        )
            except (IndexError, ValueError) as e:
                print(f"Error parsing edge line: {line}, error: {e}")
                continue

    print(f"[DEBUG] Parsed {len(topology['nodes'])} nodes and {len(topology['edges'])} edges")
    return topology


def dict_to_net_file(topology_dict):
    """Generate net file content from topology dictionary."""
    lines = ["# Generated Topology with SM nodes", "#"]

    # Sort nodes by type (Switches first, then HCAs)
    nodes = sorted(topology_dict["nodes"], key=lambda n: (n["type"] != "Switch", n["id"]))

    for node in nodes:
        # Write node definition
        lines.append(f'{node["type"]}\t{node["ports"]}\t"{node["id"]}"')

        # Find all edges for this node
        node_edges = []
        for edge in topology_dict["edges"]:
            if edge["source"] == node["id"]:
                node_edges.append(
                    {"port": edge["sourcePort"], "remote": edge["target"], "remote_port": edge["targetPort"]}
                )
            elif edge["target"] == node["id"]:
                node_edges.append(
                    {"port": edge["targetPort"], "remote": edge["source"], "remote_port": edge["sourcePort"]}
                )

        # Sort edges by port number
        node_edges.sort(key=lambda e: e["port"])

        # Write edges
        for edge in node_edges:
            lines.append(f'[{edge["port"]}]\t"{edge["remote"]}"[{edge["remote_port"]}]')

        # Add blank line after each node
        lines.append("")

    return "\n".join(lines)


def topology_to_cytoscape_json(topology_dict):
    """Convert topology dictionary to Cytoscape.js JSON format."""
    elements = []

    # Add nodes
    for node in topology_dict["nodes"]:
        elements.append(
            {
                "data": {"id": node["id"], "label": node["id"], "type": node["type"], "ports": node["ports"]},
                "classes": "switch" if node["type"] == "Switch" else "hca",
            }
        )

    # Add edges
    for edge in topology_dict["edges"]:
        elements.append(
            {
                "data": {
                    "id": edge["id"],
                    "source": edge["source"],
                    "target": edge["target"],
                    "sourcePort": edge["sourcePort"],
                    "targetPort": edge["targetPort"],
                    "label": f"[{edge['sourcePort']}] ↔ [{edge['targetPort']}]",
                }
            }
        )

    return json.dumps(elements)
