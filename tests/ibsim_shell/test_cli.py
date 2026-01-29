"""Tests for the ibsim_shell CLI."""

import os
from unittest.mock import patch, MagicMock
import pytest
from ibsim_shell.cli import main


@patch("ibsim_shell.cli.read_net_file")
@patch("ibsim_shell.cli.parse_net_to_dict")
@patch("ibsim_shell.cli.questionary.select")
@patch("os.execlpe")
def test_cli_success(mock_execlpe, mock_select, mock_parse, mock_read):
    """Test successful CLI execution flow."""
    # Setup mocks
    mock_read.return_value = 'Switch 32 "spine-01"\nHca 2 "host-01"'
    mock_parse.return_value = {"nodes": [{"id": "spine-01", "type": "Switch"}, {"id": "host-01", "type": "Hca"}]}

    mock_question = MagicMock()
    mock_select.return_value = mock_question
    mock_question.ask.return_value = "host-01"

    # Run
    main()

    # Verify
    mock_select.assert_called_once()
    mock_execlpe.assert_called_once()

    args = mock_execlpe.call_args[0]
    # args[0] is shell path, args[1] is shell path, args[2] is env
    assert args[2]["SIM_HOST"] == "host-01"
    if os.path.exists("/usr/lib/umad2sim/libumad2sim.so"):
        assert args[2]["LD_PRELOAD"] == "/usr/lib/umad2sim/libumad2sim.so"


@patch("ibsim_shell.cli.read_net_file")
def test_cli_no_net_file(mock_read):
    """Test CLI exit when net file is empty."""
    mock_read.return_value = ""

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


@patch("ibsim_shell.cli.read_net_file")
@patch("ibsim_shell.cli.parse_net_to_dict")
def test_cli_no_hcas(mock_parse, mock_read):
    """Test CLI exit when no HCAs are found in topology."""
    mock_read.return_value = 'Switch 32 "spine-01"'
    mock_parse.return_value = {"nodes": [{"id": "spine-01", "type": "Switch"}]}

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


@patch("ibsim_shell.cli.read_net_file")
@patch("ibsim_shell.cli.parse_net_to_dict")
@patch("ibsim_shell.cli.questionary.select")
def test_cli_cancel(mock_select, mock_parse, mock_read):
    """Test CLI exit when user cancels selection."""
    mock_read.return_value = 'Hca 2 "host-01"'
    mock_parse.return_value = {"nodes": [{"id": "host-01", "type": "Hca"}]}

    mock_question = MagicMock()
    mock_select.return_value = mock_question
    mock_question.ask.return_value = None  # Cancelled

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
