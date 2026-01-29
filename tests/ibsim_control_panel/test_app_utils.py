"""Test application utilities."""

import sys
from unittest.mock import MagicMock, patch, mock_open

# Mock nicegui before importing app
mock_ui = MagicMock()
mock_nicegui_app = MagicMock()
# We need to mock nicegui module structure
sys.modules["nicegui"] = MagicMock()
sys.modules["nicegui"].ui = mock_ui
sys.modules["nicegui"].app = mock_nicegui_app

# Now import the module under test
from ibsim_control_panel import app  # noqa: E402


def setup_function():
    """Reset mocks before each test."""
    mock_ui.reset_mock()
    app.mermaid_view = MagicMock()


def test_get_hca_names():
    """Test getting HCA names from topology."""
    # Mock read_net_file to return a known topology
    sample_net = """
Switch 36 "S-1"
Hca 2 "H-1"
Hca 2 "H-2"
"""
    with patch("ibsim_control_panel.app.read_net_file", return_value=sample_net):
        names = app.get_hca_names()
        assert "H-1" in names
        assert "H-2" in names
        assert "S-1" not in names
        assert len(names) == 2


def test_get_hca_names_empty():
    """Test getting HCA names when file is empty or error occurs."""
    with patch("ibsim_control_panel.app.read_net_file", side_effect=Exception("Error")):
        names = app.get_hca_names()
        assert names == []


def test_read_opensm_conf_exists():
    """Test reading opensm.conf when it exists."""
    with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open(read_data="conf data")):
        content = app.read_opensm_conf()
        assert content == "conf data"


def test_read_opensm_conf_not_exists():
    """Test reading opensm.conf when it does not exist."""
    with patch("os.path.exists", return_value=False):
        content = app.read_opensm_conf()
        assert content == ""


def test_save_opensm_conf():
    """Test saving opensm.conf."""
    m_open = mock_open()
    with patch("builtins.open", m_open):
        app.save_opensm_conf("new config")

    m_open.assert_called_with(app.OPENSM_CONF, "w")
    m_open().write.assert_called_with("new config")
    mock_ui.notify.assert_called_with("OpenSM configuration saved!", type="positive")


def test_save_net_file():
    """Test saving net file."""
    m_open = mock_open()
    with patch("builtins.open", m_open):
        app.save_net_file("new topology")

    m_open.assert_called_with(app.NET_FILE, "w")
    m_open().write.assert_called_with("new topology")
    mock_ui.notify.assert_called_with("Network topology saved!", type="positive")

    # Check if mermaid view was updated
    # app.mermaid_view is mocked in setup
    assert app.mermaid_view.content is not None
