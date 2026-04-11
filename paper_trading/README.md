# Paper trading agents (Discord, 24/7)

Simulation only: **no real orders**. Prices come from **yfinance** (free, delayed / best-effort). This is adequate for experimentation, not for production trading decisions.

## Security (read first)

- If your Discord bot token was ever pasted in chat or committed to git, **revoke it** in the [Discord Developer Portal](https://discord.com/developers/applications) and create a new token.
- Put secrets only in `.env` on the server. Never commit `.env`.

## Layout

- `paper_agent/broker/` — EUR cash, positions, variable fees (percent + minimum + spread proxy)
- `paper_agent/strategies/` — momentum, mean reversion, random, hybrid
- `paper_agent/learning/` — per-agent online adaptation (win-rate scaling, hybrid branch weights, incremental `SGDClassifier` on hybrid)
- `paper_agent/market/` — async yfinance price feed
- `paper_agent/persistence/` — CSV trade logs under `data/`
- `paper_agent/discord_bot/` — one channel per strategy + leaderboards for summaries and CSV attachments

## Channel mapping (your server)

| Strategy      | Default channel name   |
|---------------|------------------------|
| Momentum      | `agent-momentum`       |
| Mean reversion| `agent-mean-reversion` |
| Random        | `agent-random`         |
| Hybrid        | `agent-reversion`      |
| Reports / CSV | `leaderboards`         |

Override names in `.env` if needed (see `.env.example`).

## Local / server setup (Ubuntu, Python 3.10)

1. **Upload code** (from your PC), e.g. with `scp` (adjust key path):

   ```bash
   scp -i /path/to/your-key -r ./paper_trading ubuntu@82.70.90.205:~/
   ```

2. **SSH in**:

   ```bash
   ssh -i /path/to/your-key ubuntu@82.70.90.205
   ```

3. **Create venv and install**:

   ```bash
   cd ~/paper_trading
   python3.10 -m venv .venv
   source .venv/bin/activate
   pip install -U pip wheel
   pip install -r requirements.txt
   ```

4. **Configure**:

   ```bash
   cp .env.example .env
   nano .env
   ```

   Set `DISCORD_BOT_TOKEN`, confirm `DISCORD_GUILD_ID`, and tune `WATCHLIST` / fees if you want.

5. **Invite the bot** with **applications.commands** scope if you add slash commands later; for posting only, ensure the bot role can **View channel** and **Send messages** in those channels.

6. **Run manually (test)**:

   ```bash
   cd ~/paper_trading
   source .venv/bin/activate
   python -m paper_agent.main
   ```

7. **Run 24/7 with systemd** (recommended on Oracle Cloud):

   ```bash
   sudo cp deploy/paper-trading.service /etc/systemd/system/paper-trading.service
   sudo sed -i 's|/home/ubuntu/paper_trading|'$(eval echo ~ubuntu)'/paper_trading|g' /etc/systemd/system/paper-trading.service
   # Or edit WorkingDirectory/ExecStart paths to match where you cloned the repo.
   sudo systemctl daemon-reload
   sudo systemctl enable --now paper-trading
   sudo systemctl status paper-trading
   ```

   Logs:

   ```bash
   journalctl -u paper-trading -f
   ```

### Why systemd instead of tmux?

- Restarts the process if it crashes  
- Starts on server reboot  
- Centralized logs via `journalctl`  

Use tmux only for quick tests.

## Schedules

- **Instant** trade messages to each agent channel on each simulated BUY/SELL.
- **10:00 and 22:00** Europe/Lisbon: full report + CSV files attached to `#leaderboards`.

## Data

- Per-agent CSV: `data/trades_<slug>.csv`
- Snapshots appended on each scheduled report: `data/snapshot_<slug>.csv`

## Process manager choice

|        | systemd      | tmux/screen   |
|--------|--------------|---------------|
| Crash  | Auto-restart | Manual        |
| Boot   | Auto-start   | Manual        |
| Logs   | journalctl   | scrollback    |

**Use systemd** for this workload.

## Free price data note

**yfinance** is unofficial and may rate-limit or return delayed quotes. For a stricter crypto feed you could add CoinGecko later; the code is structured so you can swap `PriceFeed` without touching strategies.
