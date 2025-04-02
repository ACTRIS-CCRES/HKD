#!/usr/bin/env python
"""Script to create stats table for all CHM15k stations."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import click
import numpy as np
import pandas as pd
from influxdb_client import InfluxDBClient

from utils import influxdb, utils

__VERSION__ = "0.1.0"

# Directories
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"


# logger main configuration
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
LOG_FMT = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger(__name__)
logger_root = logging.getLogger()
# root logger need to be set to lower level to allow all loggers to log to all levels
logger_root.setLevel(logging.DEBUG)


@click.group(invoke_without_command=True, no_args_is_help=True)
@click.option(
    "--verbose",
    "-v",
    type=click.Choice(list(LOG_LEVELS.keys())),
    default="INFO",
)
@click.version_option(__VERSION__)
def grafana(verbose: str) -> None:
    """Grafana CCRES cli tool."""
    # logger for console
    ch = logging.StreamHandler()
    ch.setLevel(LOG_LEVELS[verbose])
    ch.setFormatter(LOG_FMT)

    logger.addHandler(ch)


@grafana.command()
@click.argument(
    "config-file",
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        path_type=Path,
    ),
)
@click.argument(
    "output_json",
    type=click.Path(
        exists=False,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        path_type=Path,
    ),
)
def stats(config_file: Path, output_json: str) -> None:
    """Compute statistics on housekeeping variables from Grafana data."""
    logger.info("Computing statistics for housekeeping data...")

    # Read config file
    config = utils.read_conf(config_file)

    # Read list of HKDS to monitor
    hkds = config["hkds"]["chm15k"]["param"]

    # Compute statistics
    stats_df = compute_statistics(config, hkds)

    # Save as json file
    with open(output_json, "w") as fichier: # noqa : PTH123
        json.dump(stats_df, fichier, indent=4)
    logger.info("Statistics saved in %s", output_json)

    return 0


def compute_statistics(config: dict, hkds: list[str]) -> pd.DataFrame:
    """Fetch data from InfluxDB and compute statistics."""
    # Connexion InfluxDB
    influx_config = config["influxdb"]
    client = InfluxDBClient(
        url=f"{influx_config['url']}:{influx_config['port']}",
        token=influx_config["token"],
        org=influx_config["org"],
        enable_gzip=True,
        debug=True,
    )
    query_api = client.query_api()

    # CCRES stations
    logger.info("Getting CCRES stations...")

    # Get data from tag site_id
    # ----------------------------------------------------------------------------------
    influx_api = influxdb.Influx(
        influx_config["url"],
        influx_config["token"],
        influx_config["org"],
        influx_config["port"],
    )
    list_ccres_sites = influx_api.get_list_sites(
        bucket=influx_config["bucket"],
        tag="site_id",
    )

    logger.info(
        "%d CCRES stations: %s",
        len(list_ccres_sites),
        ", ".join(list_ccres_sites),
    )

    # Dates to get the last month
    now = datetime.now()  # noqa: DTZ005
    first_day_this_month = now.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)
    start_of_last_month = first_day_last_month.strftime("%Y-%m-%dT00:00:00Z")
    end_of_last_month = last_day_last_month.strftime("%Y-%m-%dT23:59:59Z")

    dict_site = {}

    for site in list_ccres_sites:
        logger.info(
            "station %s",
            site,
        )
        dict_site[site] = {}
        for hkd in hkds:
            logger.info(
                "hkd %s",
                hkd,
            )
            dict_site[site][hkd] = {}
            query = f"""
                from(bucket: "{influx_config["bucket"]}")
                  |> range(start: {start_of_last_month}, stop: {end_of_last_month})
                  |> filter(fn: (r) => r["_measurement"] == "housekeeping")
                  |> filter(fn: (r) => r["instrument_id"] == "chm15k")
                  |> filter(fn: (r) => r["_field"] == "{hkd}")
                  |> filter(fn: (r) => r["site_id"] == "{site}")
                  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            """
            data = query_api.query_data_frame(query=query)

            if len(data) > 0:
                data = data.reset_index()
                data = data.drop(
                    [
                        "result",
                        "table",
                        "_measurement",
                        "instrument_id",
                        "_start",
                        "_stop",
                        "site_id",
                    ],
                    axis=1)

                # check if several instrument PID ie multiple instruments of same type
                list_instrument_pid = pd.unique(data.instrument_pid)
                for pid in list_instrument_pid :
                    logger.info(
                        "instrument_pid %s",
                        pid,
                    )
                    data = data[data.instrument_pid == pid]
                    data = data.drop("instrument_pid", axis=1)
                    data = data.set_index(data["_time"])
                    data = data.drop(["_time"], axis=1)
                    data = data.resample("1h").mean()
                    dict_site[site][hkd][pid] = data


    if len(dict_site) == 0:
        logger.warning("No data found for the given period.")
        return pd.DataFrame()

    # Get statistics
    # ----------------------------------------------------------------------------------

    dict_stats = dict_site.copy()

    for site, site_data in dict_site.items():
        for hkd, hkd_data in site_data.items():
            for pid, data in hkd_data.items():

                cond_hkd = (data[hkd] > config["hkds"]["chm15k"]["stats_thresh"][hkd])

                if len(data) > 0:
                    dict_stats[site][hkd][pid] = int(
                        100.0
                        * len(data[cond_hkd])
                        / len(data[(data[hkd] >= 0)]),
                                        )
                else:
                    dict_stats[site][hkd][pid] = np.nan


    return dict_stats


# Point d'entrée principal
if __name__ == "__main__":
    grafana()
