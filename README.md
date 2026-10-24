# CCRES HKD tools

This repository contains tools to manage ACTRIS-CCRES influxdb and grafana.
The code is only made to work on IPSL servers.

## Installation

- Clone the repository

    ```bash
    git clone git@github.com:ACTRIS-CCRES/HKD.git
    ```

- Install the requirements

    ```bash
    cd HKD
    conda create -n hkd python=3.12
    conda activate hkd
    python -m pip install -r requirements/requirements.txt
    ```

## Configuration

- Create a configuration file using the `conf/conf_example.toml` file.

    ```TOML
    [grafana]
    url = "https://grafana.mydomain.com"
    token = "xxxx"
    influx_ql_uid = "xxxx"

    [influxdb]
    url = "http://localhost"
    org = "ORG-NAME"
    bucket = "bucket-name"
    port = 8086
    token = "xxxx"

    [instruments]
    [instruments.hatpro]
    one-site = "template_hatpro_one-station.json"

    [instruments.chm15k]
    one-site = "template_chm15k_one-station.json"

    [instruments.rpg-fmcw-94]
    one-site = "template_rpg-fmcw-94_one-station.json"

    [instruments.rpg-fmcw-35]
    one-site = "template_rpg-fmcw-35_one-station.json"

    ```

- The code use a cache directory (`cache`) to store metadata about ACTRIS-CCRES stations. The cache directory is already filled with the metadata of the stations to accelerate the processing.
- The template for the instruments dashboards are stored in the `templates` directory.

## Usage

- Before any command, load the environment variables

    ```bash
    conda activate HKD
    ```

- To list the available commands

    ```bash
    cd HKD
    python grafana.py --help
    ```

### Create dashboards

Dashboards are only available for llufft CHM15k, RPG HATPRO, RPG-FMCW-35 and RPG-FMCW-94.

- Create dashboards for all stations

    ```bash
    python grafana.py create-dashboards conf/conf.toml
    ```

- Create dashboards for a specific stations

    ```bash
    python grafana.py create-dashboards conf/conf.toml -s juelich -s palaiseau
    ```

- Create dashboards for a specific instrument

    ```bash
    python grafana.py create-dashboards conf/conf.toml -i hatpro
    ```

- Options `-s` and `-i` can be associated
- Dashboards are only created for instruments with data in InfluxDB (by default during the last 5 years, see option `--start`)

### Update the cache of instruments

The cache is updated automatically when older than one day. It can also be updated explicitly.

- Update the cache of all stations already in cache (only raw files since the last update are requested)

    ```bash
    python grafana.py update-cache
    ```

- Add a new station or rebuild the cache of a station from scratch (slow: raw files since 2023 are requested month by month)

    ```bash
    python grafana.py update-cache -s palaiseau --rebuild
    ```

### Remove dashboards of instruments not available anymore

Dashboards of instruments without data in InfluxDB (by default during the last 5 years, the retention period of the bucket) are removed.

- List the dashboards which would be removed

    ```bash
    python grafana.py clean-dashboards conf/conf.toml --dry-run
    ```

- Remove dashboards for all stations or for specific stations

    ```bash
    python grafana.py clean-dashboards conf/conf.toml
    python grafana.py clean-dashboards conf/conf.toml -s juelich -s palaiseau
    ```

## Developments

- To install the development requirements

    ```bash
    git clone git@github.com:ACTRIS-CCRES/HKD.git
    cd HKD
    conda create -n hkd python=3.12
    python -m pip install -r requirements/requirements-dev.txt
    pre-commit install
    ```

- Create a new branch

    ```bash
    git switch -c feature/my-feature
    ```

- Make your changes
- To commit your changes you need, you need to follow [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/)
- Open a pull request
