#!/usr/bin/env python
"""Script to create stats table for all CHM15k stations."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import click
import numpy as np
import pandas as pd
from influxdb_client import InfluxDBClient

from grafana.base import GrafanaAPI

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
    )
)



def stats(config_file: Path, output_json: str) -> None:
    """Compute statistics on housekeeping variables from Grafana data."""

    logger.info("Computing statistics for housekeeping data...")

    # Read config file
    config = utils.read_conf(config_file)

    # Read list of HKDS to monitor
    hkds = config["hkds"]
    hkds = hkds["hkds"]

    # Compute statistics
    stats_df  = compute_statistics(config, hkds)

    # Save as json file
    stats_df.to_json(output_json)
    logger.info(f"Statistics saved in {output_json}")

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
    sites = list_ccres_sites[:3]

    # Dates to get the last month
    now = datetime.now() # noqa: DTZ005
    first_day_this_month = now.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)
    start_of_last_month = first_day_last_month.strftime("%Y-%m-%dT00:00:00Z")
    end_of_last_month = last_day_last_month.strftime("%Y-%m-%dT23:59:59Z")

    df_all = pd.DataFrame()

    for site in sites:
        logger.info(
            "station %s",
            site,
        )
        df = pd.DataFrame()
        for hkd in hkds:
            logger.info(
                "hkd %s",
                hkd,
            )
            query = f"""
                from(bucket: "{influx_config['bucket']}")
                  |> range(start: {start_of_last_month}, stop: {end_of_last_month})
                  |> filter(fn: (r) => r["_measurement"] == "housekeeping")
                  |> filter(fn: (r) => r["instrument_id"] == "chm15k")
                  |> filter(fn: (r) => r["_field"] == "{hkd}")
                  |> filter(fn: (r) => r["site_id"] == "{site}")
                  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            """
            data = query_api.query_data_frame(query=query)

            if len(data) > 0:
                logger.info("DATA IS NOT EMPTY")
                data = data.reset_index()
                data.drop(['instrument_pid', 'result', 'table', '_measurement', 'instrument_id', '_start', '_stop', 'site_id'], axis=1, inplace=True, errors="ignore")
                data.set_index(data["_time"], inplace=True)
                data.drop(['_time'], axis=1, inplace=True, errors="ignore")
                data = data.resample("1h").mean()
                df = pd.concat([df, data])

        if len(df) > 0:
            df["site_id"] = site
            df_all = pd.concat([df_all, df])


    if len(df_all) == 0:
        logger.warning("No data found for the given period.")
        return pd.DataFrame()



    # Get statistics
    # ----------------------------------------------------------------------------------
    stats = pd.DataFrame()
    dict_stats = {}
    
    for site in sites:
        cond_site = df_all["site_id"] == site

        for hkd in hkds :
            logger.info(
                "hkd %s",
                hkd,
            )
            #logger.info("condition stats = %s", config["stats_thresh"][hkd])
            cond_hkd = df_all[hkd] > config["stats_thresh"][hkd]
            if len(df_all[cond_site & (df_all[hkd] >= 0)]) > 0:
                dict_stats[hkd] = int(100. * len(df_all[cond_site & cond_hkd]) / len(df_all[cond_site & (df_all[hkd] >= 0)]))
            else :
                dict_stats[hkd] = np.nan
            
            


        #stats_list = [
        #    optical_quality_stat,
        #    laser_quality_stat,
        #    detector_quality_stat,
        #    windows_contaminated_warning_stat,
        #    signal_quality_warning_stat,
        #]
        #stats[site] = stats_list


        stats_temp = pd.DataFrame.from_dict(dict_stats, orient="index", columns=[site])
        stats = pd.concat([stats, stats_temp], axis=1)
        logger.info(stats)

        #stats = stats.rename(index={0: 'optical quality', 1: 'laser quality', 2: 'detector quality', 3: 'windows contaminated', 4: 'signal quality'})


    return stats




# Point d'entrée principal
if __name__ == "__main__":
    grafana() 