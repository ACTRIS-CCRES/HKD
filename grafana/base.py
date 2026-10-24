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

    @property
    def url_dashboards_uid(self) -> str:
        """Get dashboards by uid url."""
        return f"{self.url_api}/dashboards/uid"

    @property
    def url_search(self) -> str:
        """Get search url."""
        return f"{self.url_api}/search"

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

    def get_dashboards(self, folder_uid: str) -> list[dict]:
        """
        Get dashboards of a folder in grafana organization.

        Parameters
        ----------
        folder_uid : str
            Folder uid.

        Returns
        -------
        list[dict]
            The list of dashboards in the folder.

        """
        params = {"type": "dash-db", "folderUIDs": folder_uid, "limit": 5000}
        resp = requests.get(
            self.url_search,
            headers=self.headers,
            params=params,
            timeout=TIMEOUT,
        )
        if resp.status_code not in HTTP_OK:
            msg = f"ERROR getting dashboards: {resp.status_code}, {resp.text}"
            raise requests.exceptions.HTTPError(msg)

        return resp.json()

    def delete_dashboard(self, dashboard_uid: str) -> dict:
        """
        Delete a dashboard in grafana organization.

        Parameters
        ----------
        dashboard_uid : str
            Dashboard uid.

        """
        resp = requests.delete(
            f"{self.url_dashboards_uid}/{dashboard_uid}",
            headers=self.headers,
            timeout=TIMEOUT,
        )
        if resp.status_code not in HTTP_OK:
            msg = f"ERROR deleting dashboard: {resp.status_code}, {resp.text}"
            raise requests.exceptions.HTTPError(msg)

        return resp.json()
