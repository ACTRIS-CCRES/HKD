#!/usr/bin/env python
"""Script to upload dashboard for all stations."""

import logging
from pathlib import Path

import click

from grafana.base import GrafanaAPI
from utils import cloudnet, utils

__VERSION__ = "0.1.0"

# Directories
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
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
@click.option(
    "--station",
    "-s",
    type=str,
    multiple=True,
    help="station to add or update",
)
def create_dashboards(config_file: Path, station: list[str]) -> int:
    """Create ACTRIS-CCRES dashboards for all stations."""
    logger.info("Creating dashboards...")
    # read configuration file
    # ----------------------------------------------------------------------------------
    config = utils.read_conf(config_file)
    instr_with_dashboards = list(config["instruments"].keys())
    logger.debug(
        "Instruments with dashboards templates: %s",
        ", ".join(instr_with_dashboards),
    )

    # Get data from cloudnet
    # ----------------------------------------------------------------------------------
    cloudnet_api = cloudnet.CloudnetAPI()
    # CCRES stations
    logger.info("Getting CCRES stations...")
    list_ccres_station = cloudnet_api.get_actris_sites()
    if station:
        # if stations selected by user, keep only them
        list_ccres_station = [
            site for site in list_ccres_station if site["id"] in station
        ]
    list_ccres_sites_id = [site["id"] for site in list_ccres_station]
    logger.info(
        "%d CCRES stations: %s",
        len(list_ccres_station),
        ", ".join(list_ccres_sites_id),
    )

    # grafana
    # ----------------------------------------------------------------------------------
    grafana = GrafanaAPI(url=config["grafana"]["url"], token=config["grafana"]["token"])

    # get existing directory in grafana organization
    # directories are name of stations
    folders_data = grafana.get_folders()
    folders_uid = {
        elt["title"]: elt["uid"]
        for elt in folders_data
        if elt["title"] in list_ccres_sites_id
    }

    logger.info("Existing folders for station: %s", ", ".join(folders_uid.keys()))

    # loop over all ccres stations
    for site in list_ccres_station:
        site_id = site["id"]
        # if only selected stations to process
        if station and site_id not in station:
            continue

        logger.info("Processing station: %s", site_id)

        # get unique instruments of the station
        logger.debug("Getting list of instruments")
        instruments_meta = cloudnet.InstrumentsList(site_id, CACHE_DIR).instruments
        instruments_id = [instrument.id for instrument in instruments_meta]

        if not instruments_id:
            logger.error("No instruments for %s. Skipping", site_id)
            continue

        logger.debug("Instruments: %s", ", ".join(instruments_id))

        for instrument in instruments_meta:
            logger.info(
                "Processing instrument: %s, %s, %s",
                instrument.id,
                instrument.pid,
                instrument.name,
            )
            pid_short = utils.short_pid(instrument.pid)

            # check if dashboard exist for instrument
            if instrument.id not in instr_with_dashboards:
                logger.info("Dashboard template for %s does not exist", instrument.id)
                continue

            # load dashboard template
            dashboard_tmpl = config["instruments"][instrument.id]["one-site"]
            dashboard_path = TEMPLATES_DIR / dashboard_tmpl
            dashboard_uid = (
                f"ccres-{instrument.id.replace('-', '')}-hkd-{site_id}-{pid_short}"
            )
            logger.debug("Dashboard template: %s", dashboard_tmpl)

            # replace tags in dashboard template
            tags_to_replace = {
                "{{dashboard_uid}}": dashboard_uid,
                "{{site_id}}": site_id,
                "{{influx_ql_uid}}": config["grafana"]["influx_ql_uid"],
                "{{pid}}": instrument.pid,
                "{{instrument_id}}": instrument.id,
                "{{pid_short}}": pid_short,
                "{{instrument_name}}": instrument.name,
            }

            dashboard = utils.create_dashboard_from_tmpl(
                dashboard_path,
                tags_to_replace,
            )

            logger.debug("Dashboard: %s", dashboard)

            # create dashboard directory if not exist
            if site_id not in folders_uid:
                logger.info("creating directory for %s ...", site_id)
                folders_uid[site_id] = grafana.create_folder(site_id)
            else:
                logger.info("Folder %s already exists", site_id)

            # create dashboard
            logger.info("dashboard UID: %s", dashboard_uid)
            grafana.create_dashboard(dashboard, folder_uid=folders_uid[site_id])

    return 0


if __name__ == "__main__":
    grafana()
