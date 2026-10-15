"""Harness for newrelic/newrelic-python-agent#1834.

Simulates the agent's harvest cycle against a local TLS server and counts/times
SSLContext.load_default_certs() invocations — the CA-store re-parse the issue
reports happens on EVERY harvest connection on Linux.

Real harvest behaviour (newrelic/core/application.py ~L1681):
    "Force close the socket connection which has been created for this
     harvest... New connection will be create automatically on the next
     harvest."  ->  self._active_session.close_connection()

HttpClient.close_connection() closes the pool and drops it, so the next
harvest builds a brand-new HTTPSConnectionPool -> new HTTPSConnection ->
new SSLContext + load_default_certs() (see newrelic/packages/urllib3/
connection.py: the `ssl_context is None` + `load_default_certs` branch).

Usage:
    python3 harness.py --mode before|after --iterations 20 --out results.json
Run once against the pristine tree (--mode before), apply fix.patch, run again
(--mode after), and diff the JSON outputs.

The TLS handshake itself is expected to FAIL (self-signed test cert is not in
the system CA store); load_default_certs() runs before the handshake, so the
count is still the exact quantity the issue is about.
"""

import argparse
import json
import socket
import ssl
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "repo"))

# --- instrumentation -------------------------------------------------------
parse_calls = []  # list of wall-time seconds per load_default_certs() call
_orig_load_default_certs = ssl.SSLContext.load_default_certs


def _counting_load_default_certs(self, purpose=ssl.Purpose.SERVER_AUTH):
    t0 = time.perf_counter()
    try:
        return _orig_load_default_certs(self, purpose)
    finally:
        parse_calls.append(time.perf_counter() - t0)


ssl.SSLContext.load_default_certs = _counting_load_default_certs

from newrelic.common.agent_http import HttpClient  # noqa: E402


# --- local TLS server ------------------------------------------------------
def run_tls_server(certfile, keyfile, ready, stop, port_holder):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile, keyfile)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    srv.settimeout(0.5)
    port_holder.append(srv.getsockname()[1])
    ready.set()
    while not stop.is_set():
        try:
            raw, _ = srv.accept()
        except socket.timeout:
            continue
        try:
            tls = ctx.wrap_socket(raw, server_side=True)
            tls.do_handshake()
            tls.close()
        except Exception:
            pass
    srv.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["before", "after"])
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    certs = HERE / "certs"
    ready, stop, ports = threading.Event(), threading.Event(), []
    t = threading.Thread(
        target=run_tls_server,
        args=(str(certs / "server.crt"), str(certs / "server.key"), ready, stop, ports),
        daemon=True,
    )
    t.start()
    ready.wait(timeout=10)
    port = ports[0]

    results = {"mode": args.mode, "iterations": args.iterations, "handshakes": 0, "errors": 0}

    # Mirror the agent: ONE long-lived HttpClient (the active session), whose
    # connection is force-closed after each harvest and rebuilt on demand.
    client = HttpClient(host="127.0.0.1", port=port)

    t_all = time.perf_counter()
    for _ in range(args.iterations):
        try:
            client._connection.urlopen("GET", "/", retries=False, timeout=5)
            results["handshakes"] += 1
        except Exception:
            # Expected: self-signed cert not in the system CA store.
            # load_default_certs() already ran by this point.
            results["errors"] += 1
        client.close_connection()  # <- the harvest "force close"
    results["loop_wall_s"] = time.perf_counter() - t_all

    stop.set()
    t.join(timeout=5)

    results["load_default_certs_calls"] = len(parse_calls)
    results["total_parse_s"] = sum(parse_calls)
    results["mean_parse_ms"] = (
        (sum(parse_calls) / len(parse_calls)) * 1000 if parse_calls else 0.0
    )
    results["parse_calls_per_iteration"] = len(parse_calls) / args.iterations
    json.dump(results, open(args.out, "w"), indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
