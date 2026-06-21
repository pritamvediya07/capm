from setuptools import setup, find_packages

setup(
    name="capm-testbed",
    version="0.1.0",
    description="Cross-Agent Provenance Manifests (CAPM) - testbed for "
                "verifiable cross-organisational information provenance.",
    packages=find_packages(exclude=("tests", "experiments")),
    python_requires=">=3.10",
    install_requires=["cryptography>=42.0.0"],
    extras_require={"test": ["pytest>=8.0.0"]},
)
