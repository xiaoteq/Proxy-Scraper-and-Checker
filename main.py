import os, sys, re, requests
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich import box

console = Console(force_terminal=True, highlight=False)

PROXY_TYPES = ["http", "https", "socks4", "socks5"]
TYPE_COLORS = {"http": "cyan", "https": "blue", "socks4": "yellow", "socks5": "magenta"}
RUN_DIR_RE  = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$')

SETTINGS: dict = {
    "threads_scrape": 50,
    "threads_check":  500,
    "timeout":        4,
    "types":          list(PROXY_TYPES),
}


def _online() -> bool:
    try:
        requests.get("https://www.google.com/", timeout=5)
        return True
    except Exception:
        return False


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def make_run_dir() -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(ts, exist_ok=True)
    return ts


def count_lines(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for ln in f if ln.strip())
    except FileNotFoundError:
        return 0


def list_run_dirs() -> list[str]:
    return sorted([d for d in os.listdir(".") if os.path.isdir(d) and RUN_DIR_RE.match(d)], reverse=True)


def print_header() -> None:
    clear()
    t = Text(justify="center")
    t.append("\n  Proxy Scraper & Checker\n", style="bold bright_cyan")
    t.append("  HTTP / HTTPS / SOCKS4 / SOCKS5\n", style="dim cyan")
    console.print(Panel(t, border_style="cyan", box=box.ROUNDED, padding=(0, 2)))


def print_menu() -> None:
    console.print()
    items = [
        ("1", "Scrape then Check",  "download proxies, then verify all"),
        ("2", "Scrape only",        "download proxies and save to folder"),
        ("3", "Check only",         "verify proxies from a previous run"),
        ("4", "Settings",           f"threads={SETTINGS['threads_check']}  timeout={SETTINGS['timeout']}s  types={','.join(SETTINGS['types'])}"),
        ("5", "Exit",               ""),
    ]
    for num, label, hint in items:
        t = Text()
        t.append(f"  {num}.  ", style="bold cyan")
        t.append(f"{label:<24}", style="white")
        if hint:
            t.append(f"  {hint}", style="dim")
        console.print(t)
    console.print()


def show_runs() -> None:
    dirs = list_run_dirs()[:6]
    if not dirs:
        return
    tbl = Table(title=Text("Recent Runs", style="bold cyan"), title_justify="left",
                box=box.SIMPLE_HEAD, border_style="dim cyan", header_style="bold cyan", padding=(0, 2))
    tbl.add_column("Folder",          style="white")
    tbl.add_column("Scraped Proxies", justify="right", style="cyan")
    tbl.add_column("Verified Live",   justify="right", style="bright_green")
    for d in dirs:
        scraped = sum(count_lines(os.path.join(d, "proxies", f"{t}.txt")) for t in PROXY_TYPES)
        live    = sum(count_lines(os.path.join(d, "working", f"{t}.txt")) for t in PROXY_TYPES)
        tbl.add_row(d, f"{scraped:,}" if scraped else "—", f"{live:,}" if live else "—")
    console.print(tbl)
    console.print()


def settings_menu() -> None:
    LABELS = {
        "threads_scrape": "Scraper threads (parallel downloads)",
        "threads_check":  "Checker threads (parallel checks)",
        "timeout":        "Connection timeout per proxy (seconds)",
        "types":          "Proxy types to process",
    }
    while True:
        print_header()
        console.print(Rule(Text("Settings", style="cyan"), style="dim cyan"))
        console.print()
        keys = list(SETTINGS.keys())
        tbl = Table(box=box.SIMPLE_HEAD, border_style="dim cyan", header_style="bold cyan", padding=(0, 2))
        tbl.add_column("No.", style="bold cyan", justify="right", min_width=3)
        tbl.add_column("Setting",       style="white")
        tbl.add_column("Current Value", style="bright_cyan")
        for i, k in enumerate(keys, 1):
            v = SETTINGS[k]
            tbl.add_row(str(i), LABELS.get(k, k), ", ".join(v) if isinstance(v, list) else str(v))
        console.print(tbl)
        console.print()
        t = Text()
        t.append("  0.", style="bold cyan")
        t.append("  Back", style="dim")
        console.print(t)
        console.print()

        ch = console.input("  Select: ").strip()
        if ch in ("0", ""):
            break
        try:
            key = keys[int(ch) - 1]
            cur = SETTINGS[key]
        except (ValueError, IndexError):
            continue

        if isinstance(cur, list):
            console.print(f"  Available: {', '.join(PROXY_TYPES)}")
            raw = console.input("  Types (comma-separated): ").strip()
            chosen = [x.strip().lower() for x in raw.split(",") if x.strip() in PROXY_TYPES]
            if chosen:
                SETTINGS[key] = chosen
        else:
            raw = console.input(f"  New value (current: {cur}): ").strip()
            if raw:
                try:
                    SETTINGS[key] = type(cur)(raw)
                except ValueError:
                    pass
        input("  Saved. Press Enter...")


def _run_scrape(proxy_dir: str) -> dict[str, int]:
    from scraper import scrape_proxies
    return scrape_proxies(types=SETTINGS["types"], output_dir=proxy_dir, threads=SETTINGS["threads_scrape"])


def _run_check(proxy_dir: str, working_dir: str) -> dict[str, int]:
    from checker import check_proxies
    return check_proxies(input_dir=proxy_dir, output_dir=working_dir,
                         types=SETTINGS["types"], threads=SETTINGS["threads_check"],
                         timeout=SETTINGS["timeout"])


def _print_scrape_summary(counts: dict[str, int], proxy_dir: str) -> None:
    total = sum(counts.values())
    tbl = Table(box=box.SIMPLE_HEAD, border_style="dim cyan", header_style="bold cyan", padding=(0, 2))
    tbl.add_column("Protocol", style="white")
    tbl.add_column("Count",    justify="right")
    tbl.add_column("Saved To", style="dim white")
    for pt, n in counts.items():
        c = TYPE_COLORS.get(pt, "white")
        tbl.add_row(Text(pt.upper(), style=c), Text(f"{n:,}", style=c),
                    os.path.join(proxy_dir, f"{pt}.txt"))
    console.print(tbl)
    console.print(Panel(Text(f"Done. {total:,} unique proxies saved to: {proxy_dir}/", style="bright_green"),
                        border_style="green", padding=(0, 2)))


def pick_run_dir() -> str | None:
    dirs = list_run_dirs()
    if not dirs:
        console.print("  No previous run folders found.")
        return None
    console.print()
    console.print(Text("  Select a folder to check:", style="bold cyan"))
    console.print()
    for i, d in enumerate(dirs[:10], 1):
        scraped = sum(count_lines(os.path.join(d, "proxies", f"{t}.txt")) for t in PROXY_TYPES)
        t = Text()
        t.append(f"  {i}.  ", style="bold cyan")
        t.append(f"{d}  ", style="white")
        t.append(f"({scraped:,} proxies)", style="dim")
        console.print(t)
    console.print()
    ch = console.input("  Enter number (Enter = most recent): ").strip()
    try:
        return dirs[int(ch) - 1] if ch else dirs[0]
    except (ValueError, IndexError):
        return dirs[0]


def main() -> None:
    if not _online():
        console.print(Panel(Text("No internet connection.", style="bold red"), border_style="red"))
        sys.exit(1)

    while True:
        print_header()
        show_runs()
        print_menu()
        ch = console.input("  Select: ").strip()

        if ch == "1":
            run_dir     = make_run_dir()
            proxy_dir   = os.path.join(run_dir, "proxies")
            working_dir = os.path.join(run_dir, "working")
            console.print(Text(f"\n  Run folder: {run_dir}\n", style="dim cyan"))
            console.print(Rule(Text("Step 1 of 2 — Scraping", style="cyan"), style="dim cyan"))
            counts = _run_scrape(proxy_dir)
            _print_scrape_summary(counts, proxy_dir)
            console.print(Rule(Text("Step 2 of 2 — Checking", style="cyan"), style="dim cyan"))
            _run_check(proxy_dir, working_dir)

        elif ch == "2":
            run_dir   = make_run_dir()
            proxy_dir = os.path.join(run_dir, "proxies")
            console.print(Text(f"\n  Run folder: {run_dir}\n", style="dim cyan"))
            console.print(Rule(Text("Scraping", style="cyan"), style="dim cyan"))
            counts = _run_scrape(proxy_dir)
            _print_scrape_summary(counts, proxy_dir)
            input("\n  Press Enter to return to menu...")

        elif ch == "3":
            print_header()
            show_runs()
            run_dir = pick_run_dir()
            if run_dir is None:
                input("  Press Enter...")
                continue
            _run_check(os.path.join(run_dir, "proxies"), os.path.join(run_dir, "working"))

        elif ch == "4":
            settings_menu()

        elif ch in ("5", "q", "Q"):
            console.print(Text("\n  Goodbye.\n", style="cyan"))
            sys.exit(0)

        else:
            console.print(Text("  Invalid option. Enter 1 to 5.", style="red"))
            input("  Press Enter...")


if __name__ == "__main__":
    main()
