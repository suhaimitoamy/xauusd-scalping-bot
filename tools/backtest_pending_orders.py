#!/usr/bin/env python3
from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

SAFE_HOURS = set(range(8, 16))


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, names=['date', 'time', 'open', 'high', 'low', 'close', 'vol'])
    df['dt'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%Y.%m.%d %H:%M')
    return df[['dt', 'open', 'high', 'low', 'close', 'vol']].set_index('dt').sort_index()


def prep(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        (df.high - df.low).abs(),
        (df.high - prev_close).abs(),
        (df.low - prev_close).abs(),
    ], axis=1).max(axis=1).clip(lower=.01)
    df['atr'] = tr.rolling(14, min_periods=14).mean()
    df['body_ratio'] = (df.close - df.open).abs() / (df.high - df.low).clip(lower=.01)
    for lb in (12, 20, 32):
        df[f'ph{lb}'] = df.high.shift(1).rolling(lb, min_periods=lb).max()
        df[f'pl{lb}'] = df.low.shift(1).rolling(lb, min_periods=lb).min()
        df[f'span{lb}'] = df[f'ph{lb}'] - df[f'pl{lb}']
    m15 = df.resample('15min', label='right', closed='right').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'vol': 'sum'}).dropna()
    h1 = df.resample('1h', label='right', closed='right').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'vol': 'sum'}).dropna()
    m15b = pd.Series(np.where(m15.close > m15.close.shift(4), 'bullish', np.where(m15.close < m15.close.shift(4), 'bearish', 'flat')), index=m15.index)
    h1b = pd.Series(np.where(h1.close > h1.close.shift(4), 'bullish', np.where(h1.close < h1.close.shift(4), 'bearish', 'flat')), index=h1.index)
    df['m15_bias'] = m15b.reindex(df.index, method='ffill')
    df['h1_bias'] = h1b.reindex(df.index, method='ffill')
    df['hour'] = df.index.hour
    return df


def common(row, direction: str) -> bool:
    if int(row.hour) not in SAFE_HOURS:
        return False
    if row.atr < 1.10 or row.atr > 6.0 or row.body_ratio < 0.35:
        return False
    if direction == 'BUY':
        return row.m15_bias == 'bullish' and row.h1_bias == 'bullish'
    return row.m15_bias == 'bearish' and row.h1_bias == 'bearish'


def signal_at(row):
    close, open_, high, low = float(row.close), float(row.open), float(row.high), float(row.low)
    body_top, body_bot = max(open_, close), min(open_, close)
    body_size = max(body_top - body_bot, .01)
    body = abs(close - open_)
    upper, lower = high - body_top, body_bot - low
    specs = [
        ('sweep', 12, 10.0, 'METHOD_HW_SWEEP_12'),
        ('sweep', 20, 13.0, 'METHOD_HIGH_WR_M15_SWEEP_SCALP'),
        ('sweep', 32, 16.0, 'METHOD_HW_SWEEP_32'),
        ('break', 12, 10.0, 'METHOD_HW_BREAK_12'),
        ('break', 20, 13.0, 'METHOD_HW_BREAK_20'),
    ]
    for typ, lb, maxspan, base in specs:
        ph = float(getattr(row, f'ph{lb}')) if not pd.isna(getattr(row, f'ph{lb}')) else np.nan
        pl = float(getattr(row, f'pl{lb}')) if not pd.isna(getattr(row, f'pl{lb}')) else np.nan
        span = float(getattr(row, f'span{lb}')) if not pd.isna(getattr(row, f'span{lb}')) else np.nan
        if pd.isna(span) or span > maxspan:
            continue
        if typ == 'sweep':
            if common(row, 'BUY') and low <= pl and close > pl and close > open_ and lower >= body_size * .5 and (pl - low) >= .30 and (close - pl) >= 1.25:
                return {'dir': 'BUY', 'method': base + '_BUY', 'signal_price': close, 'level': pl, 'typ': typ}
            if common(row, 'SELL') and high >= ph and close < ph and close < open_ and upper >= body_size * .5 and (high - ph) >= .30 and (ph - close) >= 1.25:
                return {'dir': 'SELL', 'method': base + '_SELL', 'signal_price': close, 'level': ph, 'typ': typ}
        else:
            if common(row, 'BUY') and close > ph + .45 and close > open_ and upper <= body_size * 1.0 and body >= .90:
                return {'dir': 'BUY', 'method': base + '_BUY', 'signal_price': close, 'level': ph, 'typ': typ}
            if lb != 20 and common(row, 'SELL') and close < pl - .45 and close < open_ and lower <= body_size * 1.0 and body >= .90:
                return {'dir': 'SELL', 'method': base + '_SELL', 'signal_price': close, 'level': pl, 'typ': typ}
    return None


def pending_price(sig: Dict) -> float:
    p = sig['signal_price']
    lvl = sig['level']
    offset = max(1.0, min(3.0, abs(p - lvl) * .45))
    return p - offset if sig['dir'] == 'BUY' else p + offset


def simulate(df: pd.DataFrame, expiry_bars: int = 60, max_hold_bars: int = 240) -> List[Dict]:
    rows = list(prep(df).itertuples())
    trades = []
    next_i = 60
    i = 60
    n = len(rows)
    while i < n - expiry_bars - max_hold_bars - 1:
        if i < next_i:
            i += 1
            continue
        sig = signal_at(rows[i])
        if not sig:
            i += 1
            continue
        pp = pending_price(sig)
        d = sig['dir']
        if d == 'BUY' and pp >= sig['signal_price'] - .10:
            i += 1
            continue
        if d == 'SELL' and pp <= sig['signal_price'] + .10:
            i += 1
            continue
        trigger = None
        for j in range(i + 1, min(i + 1 + expiry_bars, n)):
            if d == 'BUY' and rows[j].low <= pp:
                trigger = j
                break
            if d == 'SELL' and rows[j].high >= pp:
                trigger = j
                break
        if trigger is None:
            i += 1
            continue
        entry = pp
        sl = entry - 6 if d == 'BUY' else entry + 6
        tp1 = entry + 3 if d == 'BUY' else entry - 3
        tp2 = entry + 6 if d == 'BUY' else entry - 6
        status = 'ACTIVE'
        out = None
        out_i = None
        for k in range(trigger, min(trigger + max_hold_bars, n)):
            hi, lo = float(rows[k].high), float(rows[k].low)
            if d == 'BUY':
                if status == 'ACTIVE' and lo <= sl:
                    out, out_i = 'LOSS', k
                    break
                if hi >= tp2:
                    out, out_i = 'WIN', k
                    break
                if status == 'ACTIVE' and hi >= tp1:
                    status, sl = 'PROTECTED', entry
                    continue
                if status == 'PROTECTED' and lo <= sl:
                    out, out_i = 'PARTIAL_WIN', k
                    break
            else:
                if status == 'ACTIVE' and hi >= sl:
                    out, out_i = 'LOSS', k
                    break
                if lo <= tp2:
                    out, out_i = 'WIN', k
                    break
                if status == 'ACTIVE' and lo <= tp1:
                    status, sl = 'PROTECTED', entry
                    continue
                if status == 'PROTECTED' and hi >= sl:
                    out, out_i = 'PARTIAL_WIN', k
                    break
        if out:
            trades.append({**sig, 'pending_price': entry, 'result': out, 'signal_time': rows[i].Index, 'entry_time': rows[trigger].Index, 'exit_time': rows[out_i].Index})
            next_i = out_i + 1
            i = out_i + 1
        else:
            i += 1
    return trades


def summarize(paths: List[str], title: str):
    lines = [title]
    total = []
    for path in paths:
        trades = simulate(load_csv(path))
        wins = sum(t['result'] != 'LOSS' for t in trades)
        losses = sum(t['result'] == 'LOSS' for t in trades)
        wr = (wins / (wins + losses) * 100) if wins + losses else 0
        label = Path(path).stem.split('_')[-1]
        lines.append(f"{label}: {len(trades)} trades, {wins}W / {losses}L, WR {wr:.2f}%")
        total.extend(trades)
    wins = sum(t['result'] != 'LOSS' for t in total)
    losses = sum(t['result'] == 'LOSS' for t in total)
    wr = (wins / (wins + losses) * 100) if wins + losses else 0
    lines.append(f"TOTAL: {len(total)} trades, {wins}W / {losses}L, WR {wr:.2f}%")
    return lines


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv-dir', default='.')
    ap.add_argument('--pattern', default='DAT_MT_XAUUSD_M1_2025*.csv')
    args = ap.parse_args()
    paths = sorted(glob.glob(os.path.join(args.csv_dir, args.pattern)))
    if not paths:
        print('No CSV files found.')
        return
    print('\n'.join(summarize(paths, 'PENDING LIMIT BACKTEST')))


if __name__ == '__main__':
    main()
