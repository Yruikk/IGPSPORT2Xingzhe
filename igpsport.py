"""China iGPSPORT web API, with request signing and isolated credentials."""
import json
import time
import uuid
from datetime import datetime
from urllib.parse import urlencode

import requests
from igp_vendor.signer import WasmSigner

BASE = "https://prod.zh.igpsport.com"
ACTIVITY = "/service/web-gateway/web-analyze/activity/"
TIMEOUT = (10, 60)


class IGPSportClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "accept": "application/json, text/plain, */*",
            "origin": "https://app.igpsport.cn",
            "referer": "https://app.igpsport.cn/",
            "timezone": "Asia/Shanghai",
            "qiwu-app-version": "8.07.08",
            "x-access-key": "AKIDWebClient", "x-platform": "web",
        })
        self.signer = WasmSigner()
        self.ready = False
        self.token = None

    def request(self, method, path, payload=None, signed=True):
        body = json.dumps(payload) if payload is not None else ""
        headers = {}
        if signed:
            if not self.ready:
                key = self.request("GET", "/service/edge-core/api/public/key", signed=False)
                self.signer.init_session_key(key["secret_key"])
                self.ready = True
            stamp, nonce = str(int(time.time())), str(uuid.uuid4())
            headers.update({"x-timestamp": stamp, "x-nonce": nonce,
                "x-signature": self.signer.generate_signature(method, path, stamp, nonce, body)})
        if self.token:
            headers["authorization"] = "Bearer " + self.token
        if body:
            headers["content-type"] = "application/json"
        response = self.session.request(method, BASE + path, data=body.encode() if body else None,
                                        headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("code") != 0:
            code = result.get("code") if isinstance(result, dict) else "invalid JSON shape"
            raise RuntimeError("IGP API failed (%s), code=%s; check credentials or API changes" % (path.split("?")[0], code))
        return result.get("data")

    def login(self, username, password):
        result = self.request("POST", "/service/auth/account/login", {
            "appId": "igpsport-web", "username": username, "password": password})
        if not isinstance(result, dict) or not result.get("access_token"):
            raise RuntimeError("IGP login returned no access_token")
        self.token = result["access_token"]

    def activities(self):
        # Preserve the original recent-record scope; use details for exact timestamps.
        params = urlencode({"pageNo": 1, "pageSize": 20, "reqType": 0, "sort": 1, "sortType": 1})
        data = self.request("GET", ACTIVITY + "queryMyActivity?" + params)
        rows = data if isinstance(data, list) else data.get("rows", data.get("list")) if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError("IGP activity list format changed")
        activities = []
        for row in rows:
            # exerciseType=0 is cycling in the current CN API.
            if row.get("exerciseType") != 0:
                continue
            rid = row["rideId"]
            detail = self.request("GET", ACTIVITY + "queryActivityDetail/" + str(rid))
            dt = datetime.fromisoformat(detail["startTime"].replace("Z", "+00:00"))
            activities.append({"RideId": rid, "StartTime": dt.isoformat(sep=" ")})
        return activities

    def download(self, ride_id):
        data = self.request("GET", ACTIVITY + "getDownloadUrl/" + str(ride_id))
        url = data if isinstance(data, str) else data.get("url") if isinstance(data, dict) else None
        if not isinstance(url, str) or not url.startswith("https://"):
            raise RuntimeError("IGP download URL missing or invalid")
        # A separate request keeps the IGP token away from the file host.
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        if response.content[8:12] != b".FIT":
            raise RuntimeError("IGP download is not a FIT file")
        return response.content
