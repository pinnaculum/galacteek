# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.39] - 2020-11-15
### Added
- Support for Windows (packaged with pyinstaller as a single EXE and Zipped folder)

- Continuous Integration with Github Actions (Travis CI is still supported)
  - CI workflow for ubuntu (Bionic), MacOS and windows

### Changed
- Move from quamash to [asyncqt](https://github.com/gmarull/asyncqt) (v 0.8.0)

### Fixed
- Fix issues with libmagic and zbar on Windows
- Fix issues with IPFS paths not always treated as POSIX paths
