import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="carbontrail-kwdseymour", # Replace with your own username
    version="0.0.1",
    author="Kyle Seymour",
    author_email="kwdseymour@gmail.com",
    description="A package for tracking real-time global aviation emissions.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kwdseymour/CarbONTRAIL",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)