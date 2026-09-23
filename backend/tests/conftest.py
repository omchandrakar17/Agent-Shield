import os

# Disable operator auth for automated tests
os.environ["AGENTSHIELD_AUTH_MODE"] = "disabled"
