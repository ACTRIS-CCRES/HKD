"""Utilities to communicate with cloudnet API."""

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests
from iteration_utilities import unique_everseen

TIMEOUT = 10
# longer timeout for instruments list because lot of data to retrieve
TIMEOUT_INSTRUMENT = 60
HTTP_OK = [200]

DATE_FMT = "%Y-%m-%d"
CCRES_HKD_OLDEST_DATA = dt.datetime(2023, 1, 1, tzinfo=dt.UTC)


@dataclass
class Instrument:
    """Instrument caracteristics."""

    id: str
    pid: str
    name: str


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

    def get_actris_sites(self) -> list[str]:
        """Get actris sites."""
        resp = requests.get(self.url_sites, timeout=TIMEOUT)
        if resp.status_code not in HTTP_OK:
            msg = f"ERROR getting folders: {resp.status_code}"
            raise requests.exceptions.HTTPError(msg)

        sites_data = resp.json()

        # filter ccres station
        return [site for site in sites_data if site["actrisId"] is not None]

    def get_station_instruments(
        self,
        site_id: str,
        date_from: dt.datetime = CCRES_HKD_OLDEST_DATA,
    ) -> list[dict[str, str]]:
        """Get list of instruments for a given site."""
        try:
            resp = requests.get(
                f"{self.url_raw_files}/?site={site_id}&dateFrom={date_from:%Y-%m-%d}",
                timeout=TIMEOUT_INSTRUMENT,
            )
        except requests.exceptions.Timeout:
            msg = f"ERROR: Timeout getting list instruments for {site_id}."

        if resp.status_code not in HTTP_OK:
            msg = f"ERROR: getting list instruments for {site_id}: {resp.status_code}, {resp.text}"  # noqa: E501
            raise requests.exceptions.HTTPError(msg)

        unique_instruments = {
            (
                file["instrument"]["instrumentId"],
                file["instrument"]["pid"],
                file["instrument"]["name"],
            )
            for file in resp.json()
        }

        return [
            {"id": instrument[0], "pid": instrument[1], "name": instrument[2]}
            for instrument in unique_instruments
        ]


@dataclass
class InstrumentsList:
    """Instruments list of CCRES stations."""

    station: str
    cache_dir: Path

    instruments: list[Instrument] = field(default_factory=list)
    cache_file: Path = field(init=False)
    last_update: dt.datetime | None = None

    def __post_init__(self) -> None:
        """Manage cache files."""
        self.cache_file = self.cache_dir / f"{self.station}.json"
        if self.cache_file.exists():
            self.load_cache()

        # update cache if needed
        if self.last_update is not None:
            today = dt.datetime.now(dt.UTC)
            if (today - self.last_update) > dt.timedelta(days=1):
                self.update_cache()
        else:
            self.last_update = CCRES_HKD_OLDEST_DATA
            self.update_cache()

    def load_cache(self) -> None:
        """Load cache file."""
        with self.cache_file.open("r") as fid:
            data = json.load(fid)

        self.last_update = dt.datetime.strptime(data["last_update"], DATE_FMT).replace(
            tzinfo=dt.UTC,
        )
        for instrument in data["instruments"]:
            self.instruments.append(Instrument(**instrument))

    def update_cache(self) -> None:
        """Update cache file."""
        cloudnet = CloudnetAPI()
        instruments = cloudnet.get_station_instruments(
            self.station,
            date_from=self.last_update,
        )

        if not self.instruments:
            self.instruments = [Instrument(**instrument) for instrument in instruments]
        else:
            # instruments exists in cache. Add new instruments
            new_instr = list(
                unique_everseen(
                    [asdict(instr) for instr in self.instruments] + instruments,
                ),
            )
            self.instruments = [Instrument(**instr) for instr in new_instr]

        # save cache
        self.last_update = dt.datetime.now(dt.UTC)
        with self.cache_file.open("w") as fid:
            json.dump(
                {
                    "station": self.station,
                    "last_update": self.last_update.strftime(DATE_FMT),
                    "instruments": [
                        asdict(instrument) for instrument in self.instruments
                    ],
                },
                fid,
                indent=2,
            )
