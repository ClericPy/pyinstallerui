from setuptools import setup, find_packages
import sys
from pyinstallerui import __version__
"""
linux:
rm -rf "dist/*";rm -rf "build/*";python3 setup.py bdist_wheel;twine upload "dist/*;rm -rf "dist/*";rm -rf "build/*""
win32-git-bash:
rm -rf dist;rm -rf build;python3 setup.py bdist_wheel;twine upload "dist/*";rm -rf dist;rm -rf build;rm -rf pyinstallerui.egg-info
"""
version = __version__
if sys.version_info < (3, 7):
    sys.exit("pypinfo requires Python 3.7+")
py_version = sys.version_info
install_requires = ["questionary"]
with open("README.md", encoding="utf-8") as f:
    README = f.read()

setup(
    name="pyinstallerui",
    version=version,
    keywords=("pyinstaller tui terminal ui gui"),
    description=
    "Let everyone is able to build python script to exe with pyinstaller, without any doc reading, support python3.7+. Read more: https://github.com/ClericPy/pyinstallerui.",
    license="MIT License",
    install_requires=install_requires,
    long_description=README,
    long_description_content_type="text/markdown",
    py_modules=["pyinstallerui"],
    author="ClericPy",
    author_email="clericpy@gmail.com",
    url="https://github.com/ClericPy/pyinstallerui",
    packages=find_packages(),
    platforms="any",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
)
