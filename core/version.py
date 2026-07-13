"""CleanupOs version and release-channel metadata."""

__version__ = "2.0.0b1"
RELEASE_CHANNEL = "beta"
IS_UNSTABLE = True
RELEASE_LABEL = "BETA / UNSTABLE"

# Shown in GUI title and CLI --version
DISPLAY_VERSION = f"{__version__} ({RELEASE_LABEL})"
