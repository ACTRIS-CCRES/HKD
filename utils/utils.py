"""Utility functions for Grafana."""

import json
import tomllib
from pathlib import Path


def read_conf(file: Path) -> dict:
    """
    Read configuration file.

    Parameters
    ----------
    file : Path
        Configuration file path.

    Returns
    -------
    dict
        Configuration file content.

    """
    with file.open("rb") as fid:
        return tomllib.load(fid)


def short_pid(pid: str) -> str:
    """
    Shorten cloudnet PID to 8 characters.

    Parameters
    ----------
    pid : str
        Cloudnet PID (https://hdl.handle.net/xx.xxxxx/x.xxxxxxxxxxxxxxxx)

    Returns
    -------
    str
        Shortened PID (xxxxxxxx)

    """
    return pid.split("/")[-1].split(".")[1][0:8]


def create_dashboard_from_tmpl(tmpl_path: Path, str_to_replace: dict) -> dict:
    """
    Replace defined tags in dashboard json template and returns it.

    Parameters
    ----------
    tmpl_path : Path
        The template of the dashboard.
    str_to_replace : dict
        The dictionary with the tags to replace and their values.

    Returns
    -------
    dict
        The modified template as a dict

    """
    with tmpl_path.open() as f:
        raw_json = "".join(f.readlines())

        for key, value in str_to_replace.items():
            raw_json = raw_json.replace(key, value)

        dashboard = json.loads(raw_json)
        # force id to null to prevent problem with existing dashboard
        dashboard["id"] = None

    return dashboard
