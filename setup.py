# For producing distributions:
#   https://packaging.python.org/tutorials/packaging-projects/

import setuptools

with open("README.md", "r") as fh:
  long_description = fh.read()

setuptools.setup(
  name="pytrope",
  version="0.0.1",
  author="Dustin Lennon",
  author_email="dustin.lennon@gmail.com",
  description="Often reused code snippets",
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/dustinlennon/pytrope",
  packages=setuptools.find_packages(),
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
  ],
  python_requires='>=3.6',
  install_requires=[
    'numpy>=1.17.2',
    'pandas>=0.25.1',
    'matplotlib>=3.1.1',
    'psycopg2>=2.8.3',
    'SQLAlchemy>=1.3.9'
  ]
)
