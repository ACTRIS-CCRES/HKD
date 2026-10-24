"""Utilies for interacting with InfluxDB."""

from dataclasses import dataclass, field

from influxdb_client import InfluxDBClient


@dataclass
class Influx:
    """InfluxDB configuration class."""

    url: str
    token: str
    org: str
    port: int = 8086

    client: InfluxDBClient = field(init=False)

    def __post_init__(self) -> None:
        """Create InfluxDB client."""
        self.client = InfluxDBClient(
            url=f"{self.url}:{self.port}",
            token=self.token,
            org=self.org,
        )

    def get_list_sites(self, bucket: str, tag: str) -> list[str]:
        """
        Get list of sites in InfluxDB.

        Returns
        -------
        list[str]
            The list of sites in InfluxDB.

        """
        query = f"""
            import "influxdata/influxdb/schema"

            schema.tagValues(bucket: "{bucket}", tag: "{tag}")
        """

        query_api = self.client.query_api()

        tables = query_api.query(query)

        sites = []
        for table in tables:
            for row in table.records:
                sites += [row.values["_value"]]  # noqa: PD011

        return sites

    def get_site_instruments_pid(
        self,
        bucket: str,
        site_id: str,
        start: str = "-5y",
    ) -> set[str]:
        """
        Get PIDs of the instruments having data for a site in InfluxDB.

        Parameters
        ----------
        bucket : str
            InfluxDB bucket.
        site_id : str
            Station actris id.
        start : str, optional
            Flux duration of the period to look for data, by default "-5y".

        Returns
        -------
        set[str]
            The PIDs of the instruments with data in the period.

        """
        query = f"""
            import "influxdata/influxdb/schema"

            schema.tagValues(
                bucket: "{bucket}",
                tag: "instrument_pid",
                predicate: (r) => r.site_id == "{site_id}",
                start: {start},
            )
        """

        query_api = self.client.query_api()

        tables = query_api.query(query)

        return {row.get_value() for table in tables for row in table.records}
