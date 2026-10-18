import base64
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import requests, json
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import garth
import zipfile
import hashlib
import sys
from igpsport import IGPSportClient, TIMEOUT

def encrpt(password, public_key):
    rsa = RSA.importKey(public_key)
    cipher = PKCS1_v1_5.new(rsa)
    return base64.b64encode(cipher.encrypt(password.encode())).decode()

def syncData(username, password, garmin_email = None, garmin_password = None):
    headers = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        "Accept-Encoding" : "gzip, deflate",
    }

    if os.getenv("IGPSPORT_REGION") == "global":
        print("国际版暂时不支持")
        return False

    if not username or not password:
        raise RuntimeError("Missing USERNAME or PASSWORD secrets")
    session = requests.session()
    type = 1 #default igp

    if garmin_password is not None and garmin_password != '':
        type = 2 #garmin


    # login account
    if type == 2:
        print("同步佳明数据")

        garth.configure(domain="garmin.cn")
        garth.login(garmin_email, garmin_password)
        activities = garth.connectapi(
            f"/activitylist-service/activities/search/activities",
            params={"activityType": "cycling", "limit": 10, "start": 0, 'excludeChildren': False},
        )
    else:
        print("同步IGP数据")

        igp = IGPSportClient()
        igp.login(username, password)
        activities = igp.activities()

    # login xingzhe account
    encrypter_public_key    = "-----BEGIN PUBLIC KEY-----\nMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDmuQkBbijudDAJgfffDeeIButq\nWHZvUwcRuvWdg89393FSdz3IJUHc0rgI/S3WuU8N0VePJLmVAZtCOK4qe4FY/eKm\nWpJmn7JfXB4HTMWjPVoyRZmSYjW4L8GrWmh51Qj7DwpTADadF3aq04o+s1b8LXJa\n8r6+TIqqL5WUHtRqmQIDAQAB\n-----END PUBLIC KEY-----\n"
    safe_password           = encrpt(password, encrypter_public_key)

    url     = "https://www.imxingzhe.com/api/v1/user/login/"
    data    = {
        'account': username,
        'password': safe_password,
    }
    res     = session.post(url, json=data, headers=headers, timeout=TIMEOUT)
    if res.status_code != 200:
        print("行者登录失败")
        return False
    result  = json.loads(res.text, strict=False)
    print("用户名:%s" % result['data']['username'])

    # Paginate destination records so older rides are not uploaded again.
    data = []
    offset = 0
    seen_pages = set()
    while True:
        url = "https://www.imxingzhe.com/api/v1/pgworkout/?offset=%s&limit=100&sport=3&year=&month=" % offset
        res = session.get(url, headers=headers, timeout=TIMEOUT)
        res.raise_for_status()
        page = res.json()["data"]["data"]
        if not isinstance(page, list):
            raise RuntimeError("Xingzhe workout list format changed")
        fingerprint = json.dumps(page, sort_keys=True)
        if page and fingerprint in seen_pages:
            raise RuntimeError("Xingzhe pagination returned a repeated page")
        seen_pages.add(fingerprint)
        data.extend(page)
        if len(page) < 100:
            break
        offset += len(page)

    sync_data = []
    # get not upload activity
    timezone = ZoneInfo('Asia/Shanghai')  # to Shanghai timezero in Gtihub Action env

    for activity in activities:
        if type == 2: #garmin
            dt        = datetime.strptime(activity["startTimeLocal"], "%Y-%m-%d %H:%M:%S")
            dt2       = dt.replace(tzinfo=timezone) if dt.tzinfo is None else dt
            s_time    = dt2.timestamp()
            mk_time   = int(s_time) * 1000
        else:
            dt        = datetime.fromisoformat(activity["StartTime"])
            dt2       = dt.replace(tzinfo=timezone) if dt.tzinfo is None else dt
            s_time    = dt2.timestamp()
            mk_time   = int(s_time) * 1000

        need_sync = True

        for item in data:
            if item["start_time"] == mk_time:
                need_sync = False
                break
        if need_sync:
            sync_data.append(activity)

    if len(sync_data) == 0:

        print("nothing data need sync")

    else:
        #down file
        upload_url = "https://www.imxingzhe.com/api/v1/fit/upload/"
        for sync_item in sync_data:
            if type == 2:  # garmin
                rid     = sync_item['activityId']
                rid = str(rid)
                print("sync rid:" + rid)
                res = garth.download(
                    f"/download-service/files/activity/{rid}",
                )
                with open(rid+".zip", "wb") as f:
                    f.write(res)
                with zipfile.ZipFile(rid+".zip", 'r') as zip_ref:
                    zip_ref.extractall(rid)
                with open(rid+"/"+rid+"_ACTIVITY.fit", 'rb') as fd:
                    data = fd.read()
                    result = session.post(upload_url, timeout=TIMEOUT, files={
                        "file_source": (None, "undefined", None),
                        "fit_filename": (None, rid+"_ACTIVITY.fit", None),
                        "md5": (None, hashlib.md5(data).hexdigest(), None),
                        "name": (None, 'Garmin-' + sync_item["startTimeLocal"], None),
                        "sport": (None, 3, None),  # 骑行
                        "fit_file": (rid+"_ACTIVITY.fit", data, 'application/octet-stream')
                    })
            else:
                rid     = sync_item["RideId"]
                rid     = str(rid)
                print("sync rid:" + rid)


                fit_data = igp.download(rid)
                result = session.post(upload_url, timeout=TIMEOUT, files={
                    "file_source": (None, "undefined", None),
                    "fit_filename": (None, sync_item["StartTime"]+'.fit', None),
                    "md5": (None, hashlib.md5(fit_data).hexdigest(), None),
                    "name": (None, 'IGPSPORT-'+sync_item["StartTime"], None),
                    "sport": (None, 3, None),  # 骑行
                    "fit_file": (sync_item["StartTime"]+'.fit', fit_data, 'application/octet-stream')
                })

            result.raise_for_status()
            payload = result.json()
            if payload.get("success") is False or ("code" in payload and payload["code"] not in (0, 200)):
                raise RuntimeError("Xingzhe rejected FIT upload")
            print("upload request completed; verify the ride in Xingzhe")
    return True

if __name__ == "__main__":
    try:
        success = syncData(os.getenv("USERNAME"), os.getenv("PASSWORD"), os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
    except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError) as exc:
        # Do not print signed URLs, tokens or credential-bearing response bodies.
        print("Sync failed: %s" % type(exc).__name__)
        if isinstance(exc, RuntimeError):
            print(str(exc))
        sys.exit(1)
    sys.exit(0 if success else 1)
