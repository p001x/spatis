"""
General-purpose "paste any link, get file bytes" resolver.

Used by Sample Digitization to import a single image/GeoTIFF from a link.
Implemented as a chain of handlers — one per source category — tried in
order: link shorteners are expanded first (since they can mask any other
category), then known share-link hosts are rewritten to their direct-file
form, then the bytes are actually fetched.

Categories that are honestly supported (no extra credentials needed, and
verified to work without an API key):
- Direct HTTP(S) file URLs (any extension), including S3, GCS (https or
  gs://), and Azure Blob URLs that are public or already carry a token/SAS
  in the query string.
- Google Drive: a single file shared as "Anyone with the link" (file/open/uc
  link shapes), including the large-file virus-scan interstitial.
- Dropbox: a single shared file link (rewritten to force a direct download).
- OneDrive / 1drv.ms: a single shared file link (via the public, no-auth
  OneDrive "shares" API — no OneDrive account or app registration needed).
- GitHub "blob" page links (rewritten to raw.githubusercontent.com).
- Link shorteners (bit.ly, tinyurl, goo.gl, t.co, ow.ly, is.gd, buff.ly,
  rebrand.ly) — expanded via redirect before the checks above run.
- ftp:// links (anonymous or user:pass embedded in the URL).

Categories that are deliberately rejected with a clear, specific message,
because supporting them for real would need credentials/APIs this project
doesn't have configured — no mocked/fake fetches are implemented for these:
- Drive/Dropbox *folders* and Google Photos albums (need OAuth + the Drive/
  Photos API to list contents).
- Gmail/Outlook attachment links (need OAuth against the mail API).
- Box share links (no reliable anonymous direct-download without the Box API).
- Imgur/Flickr *albums* (need that service's API to list images; single
  direct image links like i.imgur.com/x.jpg work fine as plain URLs).
- WMS/WMTS/XYZ tile templates/ArcGIS ImageServer (these serve rendered
  tiles/layers on demand, not one downloadable file).
- SFTP (needs login credentials + an SFTP client).
- Google Earth Engine asset IDs (already live in GEE's own storage — not
  something to "download" via a link).

Note on Cloud-Optimized GeoTIFFs: this resolver always downloads the full
file (capped, see `max_mb`) rather than remote-streaming just the needed
tiles via GDAL's /vsicurl/. That matches how this feature actually uses the
image (loaded whole into memory for map preview + digitization), so partial
streaming would add real complexity for no benefit here.
"""

from __future__ import annotations

import base64
import re
import urllib.request
from urllib.parse import urlparse

import requests

DEFAULT_TIMEOUT = 30

_SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly", "rebrand.ly",
}

_DRIVE_ID_PATTERNS = [
    re.compile(r"/d/([a-zA-Z0-9_-]{15,})"),
    re.compile(r"[?&]id=([a-zA-Z0-9_-]{15,})"),
]

_GEE_ASSET_PATTERN = re.compile(r"^(users/[\w.-]+/|projects/[\w.-]+/assets/)")


class LinkResolutionError(ValueError):
    """Raised for any link that can't honestly be resolved to a single fetchable file."""


def _expand_shortlink(url: str) -> str:
    """Follow redirects for known link-shortener domains before pattern matching.

    1drv.ms is intentionally excluded — the OneDrive direct-download trick needs
    the *original* share URL, not wherever it redirects to.
    """
    host = urlparse(url).netloc.lower()
    if host not in _SHORTENER_DOMAINS:
        return url
    try:
        resp = requests.head(url, allow_redirects=True, timeout=DEFAULT_TIMEOUT)
        if resp.url and resp.url != url:
            return resp.url
        # Some shorteners don't answer HEAD requests (405) — fall back to a streamed GET.
        resp = requests.get(url, allow_redirects=True, timeout=DEFAULT_TIMEOUT, stream=True)
        resp.close()
        return resp.url or url
    except requests.RequestException:
        return url  # let the real fetch attempt surface the real error


def _reject_unsupported(url: str) -> None:
    """Raise a clear, specific error for categories this project can't honestly support."""
    lower = url.lower()
    host = urlparse(url).netloc.lower()

    if "drive.google.com" in host and "/folders/" in lower:
        raise LinkResolutionError(
            "This is a Google Drive **folder** link. Listing folder contents needs the Drive "
            "API with OAuth, which isn't set up in this project. Open the folder, then paste a "
            "link to one file at a time instead."
        )
    if "photos.app.goo.gl" in host or "photos.google.com" in host:
        raise LinkResolutionError(
            "Google Photos share links need the Google Photos Library API (OAuth), which isn't "
            "set up in this project. Download the image from Google Photos, then upload it or "
            "host it somewhere with a plain file link instead."
        )
    if "mail.google.com" in host or "outlook.office.com" in host:
        raise LinkResolutionError(
            "Email attachment links need OAuth against the Gmail/Outlook API, which isn't set up "
            "here. Open the email, save the attachment (or grab the Drive/Dropbox link inside the "
            "email body) and paste that link instead."
        )
    if "dropbox.com" in host and "/sh/" in lower:
        raise LinkResolutionError(
            "This is a Dropbox **folder** link. Listing folder contents needs the Dropbox API, "
            "which isn't set up in this project. Open the folder, then paste a link to one file "
            "at a time instead."
        )
    if "app.box.com" in host:
        raise LinkResolutionError(
            "Box share links can't be downloaded reliably without the Box API (OAuth), which "
            "isn't set up in this project. Download the file from Box, then upload it or host it "
            "somewhere with a plain file link instead."
        )
    if ("imgur.com" == host or "imgur.com" in host and host != "i.imgur.com") and re.search(r"/(a|gallery)/", lower):
        raise LinkResolutionError(
            "This is a photo **album/gallery** link, not a single file — listing it needs that "
            "service's API. Open the album and paste a link to one direct image instead (e.g. "
            "i.imgur.com/XXXX.jpg)."
        )
    if "flickr.com" in host:
        raise LinkResolutionError(
            "Flickr links need the Flickr API to resolve to a downloadable image, which isn't "
            "set up in this project."
        )
    if re.search(r"/(wms|wmts)\b", lower) or "request=getmap" in lower or "/imageserver" in lower:
        raise LinkResolutionError(
            "This looks like a map **service** endpoint (WMS/WMTS/ArcGIS ImageServer) — it serves "
            "rendered tiles/layers on demand, not a single downloadable file. This resolver only "
            "imports single files."
        )
    if "{z}/{x}/{y}" in lower:
        raise LinkResolutionError(
            "This is an XYZ tile template — it serves individual map tiles on demand, not one "
            "downloadable file."
        )
    if lower.startswith("sftp://"):
        raise LinkResolutionError(
            "SFTP links need login credentials and an SFTP client, which isn't set up in this "
            "project. Use an anonymous FTP or HTTPS link instead."
        )
    if not lower.startswith(("http://", "https://", "ftp://")) and _GEE_ASSET_PATTERN.match(url.strip()):
        raise LinkResolutionError(
            "This looks like a Google Earth Engine asset ID, not a downloadable link — it already "
            "lives in Earth Engine's own storage. This resolver is for importing external files "
            "from a URL, not for loading existing GEE assets."
        )


def _rewrite_known_hosts(url: str) -> str:
    """Rewrite share links from known hosts into direct-download form.

    Handled here (reliable, no extra credentials needed): GitHub blob pages,
    Dropbox, `gs://` URIs, OneDrive/1drv.ms. Google Drive is handled
    separately in `_fetch_drive` since it needs a session for the
    virus-scan interstitial on larger files.
    """
    stripped = url.strip()

    if stripped.startswith("gs://"):
        return "https://storage.googleapis.com/" + stripped[len("gs://"):]

    if "github.com" in stripped and "/blob/" in stripped and "raw.githubusercontent.com" not in stripped:
        return stripped.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    host = urlparse(stripped).netloc.lower()

    if "dropbox.com" in host:
        if re.search(r"[?&]dl=0\b", stripped):
            return re.sub(r"([?&])dl=0\b", r"\1dl=1", stripped)
        if "dl=1" not in stripped:
            return stripped + ("&" if "?" in stripped else "?") + "dl=1"
        return stripped

    if "onedrive.live.com" in host or "1drv.ms" in host:
        # Public, no-auth technique for anonymous OneDrive share links (Microsoft's
        # "shares" API accepts a base64-encoded form of the original share URL).
        encoded = base64.urlsafe_b64encode(stripped.encode()).decode().rstrip("=")
        return f"https://api.onedrive.com/v1.0/shares/u!{encoded}/root/content"

    return stripped


def _drive_file_id(url: str) -> str | None:
    if "drive.google.com" not in url:
        return None
    for pattern in _DRIVE_ID_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1)
    return None


def _filename_from_response(resp: requests.Response, fallback_url: str) -> str:
    disposition = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename="?([^";]+)"?', disposition)
    if m:
        return m.group(1)
    path = urlparse(fallback_url).path
    name = path.rsplit("/", 1)[-1]
    return name or "downloaded_file"


def _read_capped(resp: requests.Response, max_mb: float) -> bytes:
    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > max_mb * 1024 * 1024:
        raise LinkResolutionError(
            f"File is {int(content_length) / (1024*1024):.1f} MB, exceeds the {max_mb:.0f} MB cap."
        )
    chunks, total = [], 0
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        total += len(chunk)
        if total > max_mb * 1024 * 1024:
            raise LinkResolutionError(f"File exceeds the {max_mb:.0f} MB cap.")
        chunks.append(chunk)
    return b"".join(chunks)


def _drive_confirm_get(session: requests.Session, url: str, params: dict) -> requests.Response:
    resp = session.get(url, params=params, timeout=DEFAULT_TIMEOUT, stream=True)
    resp.raise_for_status()
    return resp


def _fetch_drive(url: str, max_mb: float) -> tuple[bytes, str, str]:
    """Google Drive file shared as 'Anyone with the link'.

    Handles the virus-scan interstitial Drive shows for larger/ambiguous files,
    across both the older confirm-token page and the current
    drive.usercontent.google.com hidden-form page, since Google has changed this
    flow more than once and a single regex no longer reliably covers it.
    """
    file_id = _drive_file_id(url)
    base = "https://drive.google.com/uc"
    params = {"id": file_id, "export": "download"}
    session = requests.Session()

    try:
        resp = _drive_confirm_get(session, base, params)
    except requests.RequestException as e:
        raise LinkResolutionError(f"Could not reach that Drive link: {e}") from e

    # Up to a couple of follow-up requests: cookie/query confirm token, the modern
    # hidden-form redirect, then a last-resort literal "confirm=t" (Google accepts
    # this for most virus-scan warnings regardless of the "real" token value).
    for attempt in range(3):
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            break  # got the actual file

        text = resp.text
        if "Quota exceeded" in text or "quota exceeded" in text.lower():
            raise LinkResolutionError(
                "This file's Google Drive download quota has been exceeded for today (too many "
                "people have downloaded it). Try again later, or ask the owner to make a direct "
                "copy available elsewhere."
            )

        action_m = re.search(r'action="(https://drive\.usercontent\.google\.com/download[^"]*)"', text)
        if action_m:
            action_url = action_m.group(1).replace("&amp;", "&")
            hidden_inputs = dict(
                re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', text)
            )
            try:
                resp = _drive_confirm_get(session, action_url, hidden_inputs)
            except requests.RequestException as e:
                raise LinkResolutionError(f"Could not reach that Drive link: {e}") from e
            continue

        token = next((v for k, v in resp.cookies.items() if k.startswith("download_warning")), None)
        if not token:
            m = re.search(r"confirm=([0-9A-Za-z_-]+)", text)
            token = m.group(1) if m else None
        if not token:
            token = "t"  # last-resort literal Google accepts for most scan warnings

        if attempt == 2 and token == "t":
            # Already tried a real token (or none existed) and the literal fallback — give up honestly.
            raise LinkResolutionError(
                "This Drive link isn't a direct file, or isn't shared as \"Anyone with the link\". "
                "Open the file, set sharing to Anyone with the link, and paste that link again."
            )

        try:
            resp = _drive_confirm_get(session, base, {**params, "confirm": token})
        except requests.RequestException as e:
            raise LinkResolutionError(f"Could not reach that Drive link: {e}") from e

    file_bytes = _read_capped(resp, max_mb)
    return file_bytes, _filename_from_response(resp, url), resp.url or url


def _fetch_ftp(url: str, max_mb: float) -> tuple[bytes, str, str]:
    try:
        with urllib.request.urlopen(url, timeout=DEFAULT_TIMEOUT) as resp:
            data = resp.read(int(max_mb * 1024 * 1024) + 1)
    except Exception as e:  # noqa: BLE001 - a bad link must never crash the app
        raise LinkResolutionError(f"Could not reach that FTP link: {e}") from e
    if len(data) > max_mb * 1024 * 1024:
        raise LinkResolutionError(f"File exceeds the {max_mb:.0f} MB cap.")
    filename = urlparse(url).path.rsplit("/", 1)[-1] or "downloaded_file"
    return data, filename, url


def _fetch_generic(url: str, max_mb: float) -> tuple[bytes, str, str]:
    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT, stream=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise LinkResolutionError(f"Could not reach that link: {e}") from e
    file_bytes = _read_capped(resp, max_mb)
    return file_bytes, _filename_from_response(resp, url), resp.url or url


def resolve_link(url: str, max_mb: float = 100) -> tuple[bytes, str, str]:
    """Resolve any of the supported link formats (see module docstring) to raw bytes.

    Returns (file_bytes, filename, resolved_url). Raises LinkResolutionError with a
    specific, honest message for anything that can't be resolved to a single file.
    """
    url = (url or "").strip()
    if not url:
        raise LinkResolutionError("Paste a link first.")

    url = _expand_shortlink(url)
    _reject_unsupported(url)
    url = _rewrite_known_hosts(url)

    if _drive_file_id(url):
        return _fetch_drive(url, max_mb)
    if url.lower().startswith("ftp://"):
        return _fetch_ftp(url, max_mb)
    if url.lower().startswith(("http://", "https://")):
        return _fetch_generic(url, max_mb)

    raise LinkResolutionError(
        f"Unrecognized link format: `{url}`. Paste a direct HTTP(S)/FTP file URL, a Google Drive "
        "file link, or one of the other supported cloud-storage link formats."
    )
