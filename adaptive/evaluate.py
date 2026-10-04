"""Paired, reproducible synthetic experiment. Never connects to operational ATCS."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean

from atcs_simulator.app.experiment import Experiment
from atcs_simulator.app.traffic import CHANGE_START, LANES
from contracts.configuration import load_config


def arrivals(seed, scenario, duration):
    """Pre-generate demand, lane, movement, speed and lane-change intent once.

    Queue-dependent admission must not change the random sequence of later cars.
    """
    rng = random.Random(seed)
    trace = []
    for second in range(duration):
        rates = dict.fromkeys('UTSB', 6)
        if scenario == 'asymmetric':
            rates = dict(U=3, T=15, S=3, B=5)
        elif scenario == 'changing':
            rates = dict(U=15, T=3, S=5, B=3) if second < duration/2 else dict(U=3,T=3,S=5,B=15)
        for direction in 'UTSB':
            if rng.random() < rates[direction]/60:
                trace.append(dict(at=second, direction=direction,
                    movement=rng.choices(['left','straight','right'], [25,55,20])[0],
                    lane=rng.choice(LANES), speed=rng.uniform(44,52),
                    change_after=rng.uniform(CHANGE_START, CHANGE_START+80)))
    return trace


def run(trace, strategy, duration, drain=450):
    experiment = Experiment(load_config(), seed=0)
    experiment.strategy = strategy
    experiment.world.demand = dict.fromkeys('UTSB', 0)
    index, max_queue, completed_waits = 0, 0, []
    states = []
    for step in range(round((duration+drain)/.1)):
        at = step*.1
        while index < len(trace) and trace[index]['at'] <= at:
            entry = trace[index]
            vehicle = experiment.world.spawn(entry['direction'], movement=entry['movement'], lane=entry['lane'])
            if vehicle:
                vehicle.speed, vehicle.change_after = entry['speed'], entry['change_after']
            index += 1
        previous = {v.id:v for v in experiment.world.vehicles}
        experiment.tick(.1)
        current = {v.id for v in experiment.world.vehicles}
        completed_waits.extend(v.wait for key,v in previous.items() if key not in current)
        queue = sum(v.stopped and not v.committed for v in experiment.world.vehicles)
        max_queue = max(max_queue, queue)
        state = (experiment.phase, experiment.active)
        if not states or states[-1]['state'] != state:
            states.append(dict(at=round(experiment.world.time,1),state=state))
        if at >= duration and not experiment.world.vehicles:
            break
    residual = experiment.world.vehicles
    waits = sorted(completed_waits+[v.wait for v in residual])
    return dict(strategy=strategy, attempted=len(trace), admitted=len(waits), refused=experiment.world.refused,
        completed=len(completed_waits), residual=len(residual), max_queue=max_queue,
        mean_stopped_seconds=round(mean(waits),2) if waits else 0,
        p95_stopped_seconds=round(waits[max(0,math.ceil(.95*len(waits))-1)],2) if waits else 0,
        max_stopped_seconds=round(max(waits,default=0),2),
        completed_mean_stopped_seconds=round(mean(completed_waits),2) if completed_waits else None,
        end_seconds=round(experiment.world.time,1), phase_changes=len(states)-1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('docs/evaluation-stage5.json'))
    parser.add_argument('--duration', type=int, default=900)
    parser.add_argument('--drain', type=int, default=450)
    parser.add_argument('--seeds', nargs='+', type=int, default=[7,29])
    args = parser.parse_args()
    if args.duration < 1 or args.drain < 0:
        parser.error('Duration must be positive and drain nonnegative')
    rows = []
    for scenario in ('balanced','asymmetric','changing'):
        for seed in args.seeds:
            trace = arrivals(seed, scenario, args.duration)
            identity = hashlib.sha256(json.dumps(trace,sort_keys=True).encode()).hexdigest()
            for strategy in ('fixed_time','adaptive'):
                result = dict(scenario=scenario,seed=seed,trace_sha256=identity,
                              **run(trace,strategy,args.duration,args.drain))
                rows.append(result)
                print(f'{scenario} seed={seed} {strategy}: {result}', flush=True)
    report = dict(duration_seconds=args.duration,drain_limit_seconds=args.drain,step_seconds=.1,
        wait_definition='Cumulative stopped time for admitted vehicles, including unfinished vehicles at end; excludes vehicles refused at boundary.',
        limitation='Synthetic geometry/demand only. Compare refusals and residuals as well as waits. No claim about field performance.',
        results=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    with args.output.with_suffix('.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


if __name__ == '__main__':
    main()
