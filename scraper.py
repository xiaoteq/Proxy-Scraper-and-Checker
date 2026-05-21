"""scraper.py — fetches proxies from 70+ sources, saves to output_dir/{type}.txt"""
import os, sys, re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.text import Text
from rich import box

disable_warnings(InsecureRequestWarning)
console = Console(force_terminal=True, highlight=False)

PROXY_RE    = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})\b')
TYPE_COLORS = {"http": "cyan", "https": "blue", "socks4": "yellow", "socks5": "magenta"}

SOURCES: dict[str, list[str]] = {
    "http": [
        "https://api.proxyscrape.com/?request=displayproxies&proxytype=http",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/http.txt",
        "https://proxyspace.pro/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
        "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
        "https://sunny9577.github.io/proxy-scraper/proxies.txt",
        "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
        "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/HTTP.txt",
        "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
        "https://raw.githubusercontent.com/saisuiu/uiu/main/free.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_anonymous/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/saisuiu/Lionkings-Http-Proxys-Proxies/main/free.txt",
        "https://raw.githubusercontent.com/saisuiu/Lionkings-Http-Proxys-Proxies/main/cnfree.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
    ],
    "https": [
        "https://api.proxyscrape.com/?request=displayproxies&proxytype=https",
        "https://proxyspace.pro/https.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
        "https://raw.githubusercontent.com/aslisk/proxyhttps/main/https.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",
    ],
    "socks4": [
        "https://api.proxyscrape.com/?request=displayproxies&proxytype=socks4",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks4.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks4/socks4.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks4.txt",
    ],
    "socks5": [
        "https://api.proxyscrape.com/?request=displayproxies&proxytype=socks5",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks5/socks5.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt",
    ],
}


def _online() -> bool:
    try:
        requests.get("https://www.google.com/", timeout=5)
        return True
    except Exception:
        return False


def _fetch(url: str, session: requests.Session) -> set[str]:
    try:
        r = session.get(url, verify=False, timeout=10)
        if r.status_code == 200:
            return set(PROXY_RE.findall(r.text))
    except Exception:
        pass
    return set()


def scrape_proxies(types: list[str] | None = None, output_dir: str = "proxies",
                   threads: int = 50) -> dict[str, int]:
    if types is None:
        types = list(SOURCES.keys())

    os.makedirs(output_dir, exist_ok=True)

    tasks = [(pt, url) for pt in types for url in SOURCES.get(pt, [])]
    results: dict[str, set[str]] = {t: set() for t in types}

    with requests.Session() as session:
        session.headers["User-Agent"] = "Mozilla/5.0"
        with Progress(
            SpinnerColumn(style="bright_cyan"),
            TextColumn("[bold cyan]Fetching {task.completed}/{task.total} sources[/bold cyan]"),
            BarColumn(bar_width=None, style="dim cyan", complete_style="bright_cyan"),
            TimeElapsedColumn(),
            console=console, transient=True,
        ) as bar:
            tid = bar.add_task("scrape", total=len(tasks))
            with ThreadPoolExecutor(max_workers=threads) as ex:
                fmap = {ex.submit(_fetch, url, session): pt for pt, url in tasks}
                for fut in as_completed(fmap):
                    results[fmap[fut]] |= fut.result()
                    bar.advance(tid)

    counts: dict[str, int] = {}
    for pt in types:
        path = os.path.join(output_dir, f"{pt}.txt")
        data = sorted(results[pt])
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(data) + ("\n" if data else ""))
        counts[pt] = len(data)

    return counts


def main() -> None:
    from datetime import datetime
    os.system("cls" if os.name == "nt" else "clear")

    ts        = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    proxy_dir = os.path.join(ts, "proxies")

    hdr = Text(justify="center")
    hdr.append("\n  Proxy Scraper\n",               style="bold bright_cyan")
    hdr.append(f"  {sum(len(v) for v in SOURCES.values())} sources\n", style="dim cyan")
    console.print(Panel(hdr, border_style="cyan", box=box.ROUNDED, padding=(0, 2)))

    if not _online():
        console.print(Text("No internet connection.", style="bold red"))
        sys.exit(1)

    console.print(Text(f"\n  Run folder: {ts}\n", style="dim cyan"))
    counts = scrape_proxies(output_dir=proxy_dir)

    total = sum(counts.values())
    for pt, n in counts.items():
        c = TYPE_COLORS.get(pt, "white")
        console.print(f"  [{c}]{pt.upper():<8}[/{c}]  {n:,}")

    console.print(Panel(Text(f"Done. {total:,} unique proxies saved to: {proxy_dir}/", style="bright_green"),
                        border_style="green", padding=(0, 2)))

    import time; time.sleep(2)
    try:
        from checker import check_proxies
        check_proxies(input_dir=proxy_dir, output_dir=os.path.join(ts, "working"))
    except ImportError:
        pass


if __name__ == "__main__":
    main()
