# Two-Bot System

This repository intentionally separates the system into two independent bots.

## Bot 1 — Trading Bot

Universe:
- 20 large/liquid U.S. stocks
- BTC-USD

Signal logic:
- RSI(14)
- WMA(45) of RSI
- timeframes: 30m, 1h, 2h
- all three must be bullish
- fresh bullish crossover on 30m
- daily trend filter
- U.S. stocks: positive 20-day relative strength vs SPY
- BTC: no SPY relative-strength requirement
- ATR-based stop
- maximum trading sleeve: 10% of account
- risk budget: 0.3% of account per trade

Stocks scan only during regular NYSE hours.
BTC scans 24/7.

## Bot 2 — Long-Term Bot

Universe:
- VOO
- QQQ
- SCHD
- JEPQ

Monthly budget:
- $500

Default allocation:
- VOO 40%
- QQQ 25%
- SCHD 20%
- JEPQ 15%

Red-day ladder:
- <= -0.5%: deploy up to 25% of that ETF's monthly bucket
- <= -1.0%: deploy up to 50%
- <= -2.0%: deploy up to 100%
- if money remains in the last 3 trading days, suggest the remainder

This bot is buy-only and does not generate sell signals.

## Telegram setup: two separate bots

In Telegram:
1. Open `@BotFather`
2. `/newbot`
3. Create a bot such as `William Trading Bot`
4. Save its token
5. Repeat `/newbot`
6. Create `William Long Term Bot`
7. Save its second token

Then obtain the chat ID for each bot/chat.

In GitHub repository:
`Settings -> Secrets and variables -> Actions -> Secrets`

Create:
- `TRADING_BOT_TOKEN`
- `TRADING_CHAT_ID`
- `LONGTERM_BOT_TOKEN`
- `LONGTERM_CHAT_ID`

Optional repository variable:
`Settings -> Secrets and variables -> Actions -> Variables`

Create:
- `TRADING_ACCOUNT_EQUITY` = `10000`

If omitted, `config.yaml` defaults to $10,000.

## Important security step

Do not keep Telegram bot tokens directly inside Python files.

If a token has previously been committed to GitHub or pasted in source code,
regenerate that token in BotFather and use the new token as a GitHub Secret.

## Upload to GitHub

Copy these files into the root of your repo:

- `config.yaml`
- `requirements.txt`
- `indicators.py`
- `market_data.py`
- `telegram_utils.py`
- `state_utils.py`
- `trading_bot.py`
- `longterm_bot.py`
- `record_longterm_purchase.py`
- `state/`
- `.github/workflows/`

You can remove/retire the old single `strategy.py` workflow once these two bots
have been tested successfully.

## Manual tests

Install:

```bash
pip install -r requirements.txt
```

Trading bot:

```bash
python trading_bot.py
```

Long-term bot:

```bash
python longterm_bot.py
```

## Recording a long-term purchase

The long-term bot does not assume you actually bought when it sends an alert.

After you manually buy, record the dollar amount:

```bash
python record_longterm_purchase.py QQQ 62.50
```

Then commit/push the changed `state/longterm_state.json` if you ran that command locally.

## Important assumption about the screenshot strategy

The screenshots say `RSI Crossover WMA-45`, so this implementation assumes:

`RSI(14)` crosses a 45-period weighted moving average calculated on the RSI series.

If the original system uses a different interpretation, update the indicator logic
before using the signal live.

## Recommended rollout

1. Keep both bots signal-only.
2. Run them for several weeks.
3. Compare alerts against charts manually.
4. Backtest before using larger size.
5. Only after validation consider connecting an official broker API.
