from setuptools import setup, find_packages

setup(
    name="bcqthub",
    version="0.1.0",
    author="Jorge Ramirez",
    author_email="jorge.ramirez@colorado.edu",
    description="BCQT Measurement Library",
    packages=find_packages(exclude=["tests", "measurements"]),
    package_dir={"bcqthub": "bcqthub"},
    install_requires=[
        "numpy",
        "pyvisa",
        "pyyaml",
    ],
    python_requires=">=3.12,<4",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
