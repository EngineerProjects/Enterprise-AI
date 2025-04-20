from setuptools import setup, find_packages
from enterprise_ai.version import __version__

setup(
    name="enterprise_ai",
    version=__version__,
    packages=find_packages(),
    # Define entry points for post-installation scripts
    entry_points={
        "console_scripts": [
            "enterprise-ai-setup=enterprise_ai.scripts.setup:main",
        ],
    },
)
