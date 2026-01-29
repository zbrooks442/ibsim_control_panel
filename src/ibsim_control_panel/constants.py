"""Constants for the IBSim Control Panel."""

import os

# Configuration directory
CONFIG_DIR = os.getenv("IBSIM_CONFIG_DIR", ".")

# File paths
NET_FILE = os.path.join(CONFIG_DIR, "net")
OPENSM_CONF = os.path.join(CONFIG_DIR, "opensm.conf")
