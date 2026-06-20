"""Connectors subpackage — pre-built tool collections for enterprise systems.

v0.1.0 ships: REST (generic), Jira, ServiceNow, Outlook (Microsoft Graph).
SharePoint / Confluence / SAP are planned for v0.2.0.
"""

from roscoe.connectors.base_connector import BaseConnector
from roscoe.connectors.jira import JiraConnector
from roscoe.connectors.outlook import OutlookConnector
from roscoe.connectors.rest_api import RESTConnector
from roscoe.connectors.servicenow import ServiceNowConnector

__all__ = [
    "BaseConnector",
    "RESTConnector",
    "JiraConnector",
    "ServiceNowConnector",
    "OutlookConnector",
]
