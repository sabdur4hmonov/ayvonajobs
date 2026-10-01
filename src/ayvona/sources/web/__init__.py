"""Website / API / RSS sources (Bosqich 16). ``SITES``: what ``/addsource web:<key>`` can switch on.

vacancy.gov.uz is not here: no documented API or robots.txt / terms we could check (decision in
docs/PROGRESS.md, Bosqich 16).
"""

from __future__ import annotations

from ayvona.sources.web.base import WebSiteInfo, WebSource
from ayvona.sources.web.remote_apis import (
    HimalayasSource,
    JobicySource,
    RemoteOkSource,
    RemotiveSource,
)
from ayvona.sources.web.rss import RssSource
from ayvona.sources.web.uzbek_sites import HhUzSource, OsonIshSource

SITES: dict[str, WebSiteInfo] = {
    info.key: info
    for info in (
        WebSiteInfo("web:himalayas", "Himalayas (masofaviy, xalqaro)", HimalayasSource),
        WebSiteInfo("web:remotive", "Remotive (masofaviy, kuniga 4 marta)", RemotiveSource),
        WebSiteInfo("web:jobicy", "Jobicy (masofaviy, soatiga 1 marta)", JobicySource),
        WebSiteInfo("web:remoteok", "Remote OK (masofaviy)", RemoteOkSource),
        WebSiteInfo(
            "web:osonish",
            "Oson Ish (davlat portali, 14 hudud)",
            OsonIshSource,
            note="sahifa tuzilishi jonli saytda tekshirilmagan — birinchi natijalarni ko'ring",
        ),
        WebSiteInfo(
            "web:hh_uz", "hh.uz (rasmiy API, token kerak)", HhUzSource, note="HH_ACCESS_TOKEN kerak"
        ),
    )
}

__all__ = ["SITES", "RssSource", "WebSiteInfo", "WebSource"]
