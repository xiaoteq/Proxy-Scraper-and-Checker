# Proxy Scraper & Checker

Tools to scrape and verify free proxies across multiple protocols.

## Support

Join our Discord server for support and updates: [Discord Link](https://discord.gg/jWdvghHGj7)

## Modules

### scraper.py

- Fetches proxies from 70+ sources concurrently.
- Saves results to `<run_folder>/proxies/{http,https,socks4,socks5}.txt`.

### checker.py

- Validates each proxy with a live connection test.
- Records country and city via geo lookup (ip-api.com).
- Saves working proxies to `<run_folder>/working/{type}.txt`, `all.txt`, and `countries/{CC}.txt`.

### main.py

- Interactive menu to run scrape, check, or both together.
- Manages settings (threads, timeout, proxy types).
- Shows a table of recent run folders with proxy counts.

## Usage

1. Run `main.py` and select an option from the menu.
2. Option 1 (Scrape then Check) runs the full pipeline automatically.
3. Results are saved in a new timestamped folder each run.

```
python main.py
```

Alternatively, run each module standalone:

```
python scraper.py   # scrape only, then auto-launches checker
python checker.py   # check only (reads from proxies/)
```
