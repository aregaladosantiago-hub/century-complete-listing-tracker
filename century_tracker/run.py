"""Collect, validate, and publish a daily observation."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .engine import advance, empty_state, failure, reports, csv_text, dollars
from .source import collect


def save_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    os.replace(temp,path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',default='.')
    args=parser.parse_args()
    root=Path(args.root)
    ready=root/'.publish-ready'
    ready.unlink(missing_ok=True)
    now=datetime.now(timezone.utc)
    day=now.astimezone(ZoneInfo('America/Chicago')).date().isoformat()
    run_id=now.strftime('%Y%m%dT%H%M%S%fZ')
    state_path=root/'data/state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else empty_state()
    if state['last_success']==day:
        ready.write_text('unchanged\n')
        print(f'{day}: already captured; daily observation is immutable')
        return 0
    raw=root/'data/raw'/run_id
    manifest=dict(run_id=run_id,date=day,started_at=now.isoformat(),source_version=1)
    try:
        rows,coverage=collect(raw)
        updated=advance(state,day,rows,coverage)
    except Exception as exc:
        manifest.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        save_json(root/'data/runs'/f'{run_id}.json',manifest)
        save_json(state_path,failure(state,day,str(exc)))
        reports(failure(state,day,str(exc)),root/'reports',day)
        ready.write_text(run_id+' rejected\n')
        print(f'Capture rejected: {exc}',file=sys.stderr)
        return 1
    snapshot=[]
    for row in rows:
        home=updated['homes'][row['home_key']]
        snapshot.append(dict(row,snapshot_date=day,advertised_price=dollars(row['price_cents']),
                             **{k:home.get(k) for k in ('first_seen','last_seen','removed_date','reappeared_date')}))
    snapshot_path=root/'data/snapshots'/f'{day}.csv';snapshot_path.parent.mkdir(parents=True,exist_ok=True)
    snapshot_path.write_text(csv_text('snapshot_date listing_id home_key address lot community url status advertised_price first_seen last_seen removed_date reappeared_date active source'.split(),snapshot),encoding='utf-8')
    save_json(root/'data/coverage'/f'{day}.json',coverage)
    save_json(state_path,updated)
    reports(updated,root/'reports',day)
    manifest.update(status='success',active=coverage['observed_active'],rows=len(rows),finished_at=datetime.now(timezone.utc).isoformat())
    save_json(root/'data/runs'/f'{run_id}.json',manifest)
    ready.write_text(run_id+' accepted\n')
    print(f"{day}: accepted {len(rows)} observations; {coverage['observed_active']} available homes")
    return 0


if __name__=='__main__':
    sys.exit(main())
