"""Test topology parsing and generation."""

import json
from ibsim_control_panel.topology import (
    parse_net_to_dict,
    dict_to_net_file,
    parse_net_to_mermaid,
    topology_to_cytoscape_json,
    read_net_file,
)
from unittest.mock import patch, mock_open

# Sample .net file content for testing
SAMPLE_NET_CONTENT = """# Sample Topology
Switch	36	"S-1"
[1]	"H-1"[1]
[2]	"H-2"[1]

Hca	2	"H-1"
[1]	"S-1"[1]

Hca	2	"H-2"
[1]	"S-1"[2]
"""

# Expected dictionary structure for the sample content
EXPECTED_TOPOLOGY_DICT = {
    "nodes": [
        {"id": "S-1", "type": "Switch", "ports": 36},
        {"id": "H-1", "type": "Hca", "ports": 2},
        {"id": "H-2", "type": "Hca", "ports": 2},
    ],
    "edges": [
        {
            "id": "S-1:1-H-1:1",
            "source": "S-1",
            "target": "H-1",
            "sourcePort": 1,
            "targetPort": 1,
        },
        {
            "id": "S-1:2-H-2:1",
            "source": "S-1",
            "target": "H-2",
            "sourcePort": 2,
            "targetPort": 1,
        },
    ],
}


def test_parse_net_to_dict():
    """Test parsing .net content to dictionary."""
    topology = parse_net_to_dict(SAMPLE_NET_CONTENT)

    # Check nodes
    assert len(topology["nodes"]) == 3

    # Check specific nodes exist
    ids = [n["id"] for n in topology["nodes"]]
    assert "S-1" in ids
    assert "H-1" in ids
    assert "H-2" in ids

    # Check edges
    assert len(topology["edges"]) == 2

    # Check first edge attributes
    edge = topology["edges"][0]
    assert edge["source"] == "S-1"
    assert edge["target"] == "H-1"
    assert edge["sourcePort"] == 1
    assert edge["targetPort"] == 1


def test_dict_to_net_file():
    """Test converting dictionary back to .net content."""
    # Convert dict to net string
    net_content = dict_to_net_file(EXPECTED_TOPOLOGY_DICT)

    # Parse it back to verify round-trip consistency
    topology_round_trip = parse_net_to_dict(net_content)

    # Sort lists to ensure comparison works (lists order might differ)
    def sort_nodes(nodes):
        return sorted(nodes, key=lambda x: x["id"])

    def sort_edges(edges):
        return sorted(edges, key=lambda x: x["id"])

    assert sort_nodes(topology_round_trip["nodes"]) == sort_nodes(EXPECTED_TOPOLOGY_DICT["nodes"])

    # Check if we have the same connections
    edges_orig = [(e["source"], e["target"], e["sourcePort"], e["targetPort"]) for e in EXPECTED_TOPOLOGY_DICT["edges"]]
    edges_rt = [(e["source"], e["target"], e["sourcePort"], e["targetPort"]) for e in topology_round_trip["edges"]]

    # Normalize edges (source/target order) for comparison as A-B is same as B-A
    def normalize_edge(e):
        n1, n2 = e[0], e[1]
        p1, p2 = e[2], e[3]
        if n1 > n2:
            return (n2, n1, p2, p1)
        return (n1, n2, p1, p2)

    assert sorted([normalize_edge(e) for e in edges_rt]) == sorted([normalize_edge(e) for e in edges_orig])


def test_parse_net_to_mermaid():
    """Test parsing .net content to Mermaid graph."""
    mermaid = parse_net_to_mermaid(SAMPLE_NET_CONTENT)

    assert "graph LR;" in mermaid
    assert 'S-1["S-1"]:::switch' in mermaid
    assert 'H-1["H-1"]:::hca' in mermaid
    assert "S-1 --- H-1" in mermaid
    assert "classDef switch" in mermaid


def test_topology_to_cytoscape_json():
    """Test converting topology dict to Cytoscape JSON."""
    json_str = topology_to_cytoscape_json(EXPECTED_TOPOLOGY_DICT)
    elements = json.loads(json_str)

    # Should have 3 nodes + 2 edges = 5 elements
    assert len(elements) == 5

    # Check for node classes
    nodes = [el for el in elements if "classes" in el]
    assert len(nodes) == 3

    s1 = next(n for n in nodes if n["data"]["id"] == "S-1")
    assert s1["classes"] == "switch"

    h1 = next(n for n in nodes if n["data"]["id"] == "H-1")
    assert h1["classes"] == "hca"


def test_parse_net_to_dict_empty():
    """Test parsing empty or comment-only content."""
    assert parse_net_to_dict("") == {"nodes": [], "edges": []}
    assert parse_net_to_dict("# Just a comment") == {"nodes": [], "edges": []}


def test_parse_net_to_dict_invalid_lines():
    """Test parsing with some invalid lines (should be skipped gracefully)."""
    content = """
    Switch 36 "S-1"
    Invalid Line Here
    [1] "S-1"[1]
    """

    topology = parse_net_to_dict(content)
    assert len(topology["nodes"]) == 1
    assert topology["nodes"][0]["id"] == "S-1"


def test_read_net_file_exists():
    """Test reading net file when it exists."""
    with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open(read_data="file content")):
        content = read_net_file()
        assert content == "file content"


def test_read_net_file_not_exists():
    """Test reading net file when it does not exist."""
    with patch("os.path.exists", return_value=False):
        content = read_net_file()
        assert content == ""
