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
