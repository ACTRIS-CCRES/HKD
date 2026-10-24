"""Utilities to communicate with cloudnet API."""

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

import requests

TIMEOUT = 10
# longer timeout for instruments list because lot of data to retrieve
TIMEOUT_INSTRUMENT = 60
HTTP_OK = [200]

DATE_FMT = "%Y-%m-%d"
CCRES_HKD_OLDEST_DATA = dt.datetime(2023, 1, 1, tzinfo=dt.UTC)
# raw files are requested by period to limit the size of responses (~10 MB/month)
RAW_FILES_PERIOD = dt.timedelta(days=30)
CACHE_VALIDITY = dt.timedelta(days=1)


@dataclass
class Instrument:
    """Instrument caracteristics."""

    id: str
    pid: str
    name: str
    is_nominal: bool = False


@dataclass
class CloudnetAPI:
    """
    Class to access cloudnet API.

    Based on docs in https://docs.cloudnet.fmi.fi/api/data-portal.html
    """

    url = "https://cloudnet.fmi.fi/api"

    @property
    def url_sites(self) -> str:
        """Get sites api url."""
        return f"{self.url}/sites"

    @property
    def url_raw_files(self) -> str:
        """Get raw files api url."""
        return f"{self.url}/raw-files"

    @property
    def url_nominal(self) -> str:
        """Get nominal api url."""
        return f"{self.url}/nominal-instrument"

    def get_actris_sites(self) -> list[str]:
        """Get actris sites."""
        resp = requests.get(self.url_sites, timeout=TIMEOUT)
        if resp.status_code not in HTTP_OK:
            msg = f"ERROR getting folders: {resp.status_code}"
            raise requests.exceptions.HTTPError(msg)

        sites_data = resp.json()

        # filter ccres station
        return [site for site in sites_data if site["actrisId"] is not None]

    def get_raw_files(
        self,
        site_id: str,
        date_from: dt.datetime,
        date_to: dt.datetime,
    ) -> list[dict]:
        """Get raw files of a site between two dates (included)."""
        params = {
            "site": site_id,
            "dateFrom": f"{date_from:{DATE_FMT}}",
            "dateTo": f"{date_to:{DATE_FMT}}",
        }
        try:
            resp = requests.get(
                self.url_raw_files,
                params=params,
                timeout=TIMEOUT_INSTRUMENT,
            )
        except requests.exceptions.Timeout as err:
            msg = f"ERROR: Timeout getting raw files for {site_id}."
            raise requests.exceptions.Timeout(msg) from err

        if resp.status_code not in HTTP_OK:
            msg = f"ERROR: getting raw files for {site_id}: {resp.status_code}, {resp.text}"  # noqa: E501
            raise requests.exceptions.HTTPError(msg)

        return resp.json()

    def get_station_instruments(
        self,
        site_id: str,
        date_from: dt.datetime = CCRES_HKD_OLDEST_DATA,
    ) -> list[dict[str, str]]:
        """
        Get list of instruments with raw files for a given site since a date.

        Instruments are unique by PID. Raw files are requested by period of
        RAW_FILES_PERIOD to avoid timeouts.
        """
        today = dt.datetime.now(dt.UTC)
        instruments = {}
        period_start = date_from
        while period_start <= today:
            period_end = min(period_start + RAW_FILES_PERIOD, today)
            for file in self.get_raw_files(site_id, period_start, period_end):
                instrument = file["instrument"]
                instruments[instrument["pid"]] = {
                    "id": instrument["instrumentId"],
                    "pid": instrument["pid"],
                    "name": instrument["name"],
                }
            period_start = period_end + dt.timedelta(days=1)

        return list(instruments.values())

    def is_instrument_nominal(
        self,
        instr_pid: str,
        site_id: str,
    ) -> bool:
        """
        Check if the instrument is nominal.

        Parameters
        ----------
        instr_pid : str
            Instrument actris pid.
        site_id : str
            Station actris id.

        Returns
        -------
        bool
            True if nominal, False otherwise.

        """
        date = dt.datetime.now(dt.UTC).strftime(DATE_FMT)

        url = f"{self.url_nominal}/?&site={site_id}&date={date}"
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code not in HTTP_OK:
            msg = f"ERROR getting nominal instruments for {site_id}: {resp.status_code}, {resp.text}"  # noqa: E501
            raise requests.exceptions.HTTPError(msg)

        # get list of pids
        nominal_pids = [instr["nominalInstrument"]["pid"] for instr in resp.json()]

        return instr_pid in nominal_pids


@dataclass
class InstrumentsList:
    """
    Instruments list of CCRES stations.

    The list is cached in a json file per station and updated from cloudnet raw
    files when the cache is older than CACHE_VALIDITY (or always if force_update).
    Instruments are unique by PID; the latest name from cloudnet is kept. With
    rebuild, the existing cache is ignored and rebuilt from CCRES_HKD_OLDEST_DATA.
    """

    station: str
    cache_dir: Path
    rebuild: bool = False
    force_update: bool = False

    instruments: list[Instrument] = field(default_factory=list)
    cache_file: Path = field(init=False)
    last_update: dt.datetime | None = None

    def __post_init__(self) -> None:
        """Manage cache files."""
        self.cache_file = self.cache_dir / f"{self.station}.json"
        if self.cache_file.exists() and not self.rebuild:
            self.load_cache()

        # update cache if needed
        if self.last_update is None:
            self.last_update = CCRES_HKD_OLDEST_DATA
            self.update_cache()
        elif (
            self.force_update
            or dt.datetime.now(dt.UTC) - self.last_update > CACHE_VALIDITY
        ):
            self.update_cache()

    def load_cache(self) -> None:
        """Load cache file."""
        with self.cache_file.open(encoding="utf-8") as fid:
            data = json.load(fid)

        self.last_update = dt.datetime.strptime(data["last_update"], DATE_FMT).replace(
            tzinfo=dt.UTC,
        )
        # older cache files may contain the same instrument several times
        instruments = {
            instrument["pid"]: Instrument(**instrument)
            for instrument in data["instruments"]
        }
        self.instruments = list(instruments.values())

    def update_cache(self) -> None:
        """Update cache with instruments having raw files since last update."""
        new_instruments = CloudnetAPI().get_station_instruments(
            self.station,
            date_from=self.last_update,
        )

        instruments = {instrument.pid: instrument for instrument in self.instruments}
        instruments.update(
            {
                instrument["pid"]: Instrument(**instrument)
                for instrument in new_instruments
            },
        )
        self.instruments = sorted(
            instruments.values(),
            key=lambda instrument: (instrument.id, instrument.name),
        )

        self.last_update = dt.datetime.now(dt.UTC)
        self.save_cache()

    def save_cache(self) -> None:
        """Save cache file."""
        # nominal status changes over time and is checked when needed
        with self.cache_file.open("w", encoding="utf-8") as fid:
            json.dump(
                {
                    "station": self.station,
                    "last_update": self.last_update.strftime(DATE_FMT),
                    "instruments": [
                        {"id": instr.id, "pid": instr.pid, "name": instr.name}
                        for instr in self.instruments
                    ],
                },
                fid,
                indent=2,
                ensure_ascii=False,
            )
            fid.write("\n")
