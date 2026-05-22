import os, sys, re, time, collections, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import (Progress, SpinnerColumn, BarColumn,
                           TextColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn)
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich import box

console = Console(force_terminal=True, highlight=False)

PROXY_TYPES = ["http", "https", "socks4", "socks5"]
TYPE_COLORS = {"http": "cyan", "https": "blue", "socks4": "yellow", "socks5": "magenta"}
PROXY_RE    = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$')

# ip-api.com: validates proxy AND returns geo in one request (free, no key needed)
GEO_URL = "http://ip-api.com/json?fields=status,country,countryCode,city"
# Fallback validation endpoints (no rate limit)
FALLBACK_URLS = ["http://httpbin.org/ip", "https://api.ipify.org"]
# Fallback geo APIs used only when ip-api.com is unavailable
GEO_FALLBACKS = [
    ("ipapi.co",  lambda ip: f"https://ipapi.co/{ip}/json/"),
    ("ipinfo.io", lambda ip: f"https://ipinfo.io/{ip}/json"),
]


def _online() -> bool:
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except Exception:
        return False


def _proxies(proxy: str, ptype: str) -> dict:
    scheme = {"socks4": "socks4", "socks5": "socks5"}.get(ptype, "http")
    url = f"{scheme}://{proxy}"
    return {"http": url, "https": url}


def _geo_fallback(ip: str) -> tuple[str, str, str]:
    for name, url_fn in GEO_FALLBACKS:
        try:
            r = requests.get(url_fn(ip), timeout=4)
            if r.status_code != 200:
                continue
            d = r.json()
            if name == "ipapi.co" and not d.get("error"):
                return d.get("country_name", "Unknown"), d.get("country_code", ""), d.get("city", "Unknown")
            if name == "ipinfo.io":
                return d.get("country", "Unknown"), d.get("country", ""), d.get("city", "Unknown")
        except Exception:
            pass
    return "Unknown", "", "Unknown"


def check_proxy(proxy: str, ptype: str, timeout: int) -> dict:
    pd = _proxies(proxy, ptype)
    t0 = time.monotonic()
    country, cc, city = "Unknown", "", "Unknown"

    # Primary: ip-api.com gives validation + geo in one shot.
    # HTTP 429 = rate-limited but proxy IS reachable, treat as alive.
    try:
        r = requests.get(GEO_URL, proxies=pd, timeout=timeout)
        if r.status_code in (200, 429):
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "success":
                    country, cc, city = d["country"], d["countryCode"], d["city"]
            return {"proxy": proxy, "type": ptype, "alive": True,
                    "country": country, "cc": cc, "city": city,
                    "latency": int((time.monotonic() - t0) * 1000)}
    except Exception:
        pass

    # Fallback: simple connectivity check, then separate geo lookup
    for url in FALLBACK_URLS:
        try:
            r = requests.get(url, proxies=pd, timeout=timeout)
            if r.status_code in (200, 201, 202):
                country, cc, city = _geo_fallback(proxy.split(":")[0])
                return {"proxy": proxy, "type": ptype, "alive": True,
                        "country": country, "cc": cc, "city": city,
                        "latency": int((time.monotonic() - t0) * 1000)}
        except Exception:
            pass

    return {"proxy": proxy, "type": ptype, "alive": False,
            "country": "Unknown", "cc": "", "city": "Unknown",
            "latency": int((time.monotonic() - t0) * 1000)}


def _save(result: dict, out_dir: str, country_dir: str) -> None:
    proxy, ptype, cc = result["proxy"], result["type"], result["cc"].upper() if result["cc"] else None
    with open(os.path.join(out_dir, f"{ptype}.txt"), "a", encoding="utf-8") as f:
        f.write(proxy + "\n")
    with open(os.path.join(out_dir, "all.txt"), "a", encoding="utf-8") as f:
        f.write(f"{ptype}://{proxy}\n")
    if cc:
        with open(os.path.join(country_dir, f"{cc}.txt"), "a", encoding="utf-8") as f:
            f.write(f"{ptype}://{proxy}\n")


def _build_display(progress: Progress, state: dict, recent: collections.deque) -> Group:
    elapsed    = max(time.time() - state["start"], 0.001)
    speed      = state["checked"] / elapsed
    total_live = sum(state["live"].values())

    # Stats grid: 4 rows x (label | value | label | value)
    sg = Table.grid(padding=(0, 3))
    sg.add_column(style="dim white", min_width=18)
    sg.add_column(min_width=10)
    sg.add_column(style="dim white", min_width=10)
    sg.add_column(min_width=10)

    sg.add_row("Live proxies",  Text(f"{total_live:,}",             style="bold bright_green"),
               "HTTP",          Text(f"{state['live']['http']:,}",   style="cyan"))
    sg.add_row("Dead proxies",  Text(f"{state['dead']:,}",          style="bold red"),
               "HTTPS",         Text(f"{state['live']['https']:,}",  style="blue"))
    sg.add_row("Speed",         Text(f"{speed:,.0f}/sec",           style="bold cyan"),
               "SOCKS4",        Text(f"{state['live']['socks4']:,}", style="yellow"))
    sg.add_row("Checked",       Text(f"{state['checked']:,}",       style="white"),
               "SOCKS5",        Text(f"{state['live']['socks5']:,}", style="magenta"))

    stats = Panel(sg, title=Text("Results", style="bold cyan"),
                  border_style="dim cyan", padding=(0, 2), box=box.ROUNDED)

    # Live proxy log: chronological order (oldest at top = ascending No.)
    tbl = Table(title=Text("Live Proxies Found", style="bold cyan"), title_justify="left",
                box=box.SIMPLE_HEAD, border_style="dim cyan", header_style="bold cyan",
                min_width=72, padding=(0, 2))
    tbl.add_column("No.",          justify="right", style="dim white", min_width=4)
    tbl.add_column("Proxy",        style="white",   min_width=22)
    tbl.add_column("Protocol",                      min_width=7)
    tbl.add_column("Country",      style="yellow",     min_width=20)
    tbl.add_column("City",         style="dim yellow", min_width=14)
    tbl.add_column("Response Time", justify="right",   min_width=12)

    # list(recent) is oldest→newest (append order); display as-is → No. ascends top-to-bottom
    for e in list(recent):
        lat = e["latency"]
        lc  = "bright_green" if lat < 1500 else "yellow" if lat < 4000 else "red"
        tbl.add_row(str(e["id"]), e["proxy"],
                    Text(e["type"].upper(), style=TYPE_COLORS.get(e["type"], "white")),
                    e["country"], e["city"], Text(f"{lat:,} ms", style=lc))

    return Group(stats, " ", progress, " ", tbl)


def check_proxies(input_dir: str = "proxies", output_dir: str = "working",
                  types: list | None = None, threads: int = 500, timeout: int = 4) -> dict[str, int]:
    if types is None:
        types = PROXY_TYPES

    os.system("cls" if os.name == "nt" else "clear")

    hdr = Text(justify="center")
    hdr.append("\n  Proxy Checker\n", style="bold bright_cyan")
    hdr.append(f"  {threads} threads  /  {timeout}s timeout\n", style="dim cyan")
    console.print(Panel(hdr, border_style="cyan", box=box.ROUNDED, padding=(0, 2)))

    if not _online():
        console.print(Panel(Text("No internet connection.", style="bold red"), border_style="red"))
        sys.exit(1)

    # Load proxies
    tasks: list[tuple[str, str]] = []
    for ptype in types:
        path = os.path.join(input_dir, f"{ptype}.txt")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                p = line.strip()
                if p and PROXY_RE.match(p):
                    tasks.append((p, ptype))

    total = len(tasks)
    if total == 0:
        console.print(Text(f"\n  No valid proxies found in: {input_dir}/", style="yellow"))
        input("\n  Press Enter to continue...")
        return {}

    # Prepare output dirs
    country_dir = os.path.join(output_dir, "countries")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(country_dir, exist_ok=True)
    for pt in PROXY_TYPES:
        open(os.path.join(output_dir, f"{pt}.txt"), "w").close()
    open(os.path.join(output_dir, "all.txt"), "w").close()

    console.print(Text(f"\n  Loaded {total:,} proxies  —  saving to {output_dir}/\n", style="dim cyan"))

    state: dict = {
        "checked": 0, "dead": 0,
        "live": {t: 0 for t in PROXY_TYPES},
        "start": time.time(),
    }
    # maxlen=12: only keep last 12 live proxies visible; append = chronological order
    recent: collections.deque = collections.deque(maxlen=12)

    progress = Progress(
        SpinnerColumn(style="bright_cyan"),
        TextColumn("[cyan]Checking proxies[/cyan]"),
        BarColumn(bar_width=None, style="dim cyan", complete_style="bright_cyan"),
        MofNCompleteColumn(),
        TextColumn("[cyan]{task.percentage:.1f}%[/cyan]"),
        TimeElapsedColumn(), TimeRemainingColumn(),
        expand=True, console=console,
    )
    tid = progress.add_task("Checking", total=total)

    with Live(refresh_per_second=8, console=console) as live:
        live.update(_build_display(progress, state, recent))

        with ThreadPoolExecutor(max_workers=threads) as ex:
            futures = {ex.submit(check_proxy, p, t, timeout): None for p, t in tasks}
            last = 0.0
            for fut in as_completed(futures):
                res = fut.result()
                progress.advance(tid)
                state["checked"] += 1
                if res["alive"]:
                    state["live"][res["type"]] += 1
                    res["id"] = sum(state["live"].values())  # global serial number
                    recent.append(res)                        # append = oldest→newest order
                    _save(res, output_dir, country_dir)
                else:
                    state["dead"] += 1

                now = time.time()
                if now - last >= 0.125:
                    live.update(_build_display(progress, state, recent))
                    last = now

        live.update(_build_display(progress, state, recent))

    # Summary
    final_live  = sum(state["live"].values())
    n_countries = len([f for f in os.listdir(country_dir) if f.endswith(".txt")]) if os.path.isdir(country_dir) else 0

    console.print()
    console.print(Panel(
        Text(f"Done.\n\n  Live proxies : {final_live:,}\n  Countries    : {n_countries}\n  Saved to     : {output_dir}/",
             style="bright_green"),
        title=Text("Summary", style="bold bright_green"), border_style="green", padding=(0, 2),
    ))

    console.print()
    tbl = Table(box=box.SIMPLE_HEAD, border_style="dim cyan", header_style="bold cyan", padding=(0, 2))
    tbl.add_column("Protocol", style="white")
    tbl.add_column("Live",     justify="right")
    tbl.add_column("File",     style="dim white")
    for pt in PROXY_TYPES:
        c = TYPE_COLORS[pt]
        tbl.add_row(Text(pt.upper(), style=c), Text(f"{state['live'].get(pt, 0):,}", style=c),
                    os.path.join(output_dir, f"{pt}.txt"))
    console.print(tbl)
    console.print()
    input("  Press Enter to continue...")
    return dict(state["live"])


def main() -> None:
    if not _online():
        console.print(Text("No internet connection.", style="bold red"))
        sys.exit(1)
    check_proxies()


if __name__ == "__main__":
    main()
