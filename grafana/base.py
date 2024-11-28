"""Module to interact with Grafana API."""

from dataclasses import dataclass

import requests

TIMEOUT = 10
HTTP_OK = [200]


@dataclass
class GrafanaAPI:
    """Grafana configuration class."""

    url: str
    token: str

    @property
    def headers(self) -> dict:
        """Get headers."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @property
    def url_api(self) -> str:
        """Get API url."""
        return f"{self.url}/api"

    @property
    def url_folders(self) -> str:
        """Get folders url."""
        return f"{self.url_api}/folders"

    @property
    def url_dashboards(self) -> str:
        """Get dashboards url."""
        return f"{self.url_api}/dashboards/db"

    def get_folders(self) -> list[dict[str, str]]:
        """
        Get folders in grafana organization.

        Returns
        -------
        list[dict]
            The list of available folders in the organisation.

        """
        resp = requests.get(self.url_folders, headers=self.headers, timeout=TIMEOUT)
        if resp.status_code not in HTTP_OK:
            msg = f"ERROR getting folders: {resp.status_code}"
            raise requests.exceptions.HTTPError(msg)

        return resp.json()

    def create_folder(self, folder_name: str) -> str:
        """
        Create a folder in grafana organization.

        Parameters
        ----------
        folder_name : str
            Folder name.

        Returns
        -------
        str
            uid in grafana of the created folder.

        """
        data = {"title": folder_name}

        resp = requests.post(
            self.url_folders,
            headers=self.headers,
            json=data,
            timeout=TIMEOUT,
        )
        if resp.status_code not in HTTP_OK:
            msg = f"ERROR creating folder: {resp.status_code}"
            raise requests.exceptions.HTTPError(msg)

        return resp.json()["uid"]

    def create_dashboard(
        self,
        dashboard: dict,
        *,  # enforce keyword only arguments
        folder_uid: str | None = None,
        overwrite: True = True,
    ) -> dict:
        """
        Create a dashboard in grafana organization.

        Parameters
        ----------
        dashboard : dict
            Dashboard json data.
        folder_uid : str, optional
            Folder uid of the dashboard, None means no folder, by default None.
        overwrite : bool, optional
            Overwrite the dashboard if it exists, by default True.

        """
        data = {"dashboard": dashboard, "overwrite": overwrite}
        if folder_uid is not None:
            data["folderUid"] = folder_uid

        resp = requests.post(
            self.url_dashboards,
            headers=self.headers,
            json=data,
            timeout=TIMEOUT,
        )
        if resp.status_code not in HTTP_OK:
            msg = f"ERROR creating dashboard: {resp.status_code}, {resp.text}"
            raise requests.exceptions.HTTPError(msg)

        return resp.json()
