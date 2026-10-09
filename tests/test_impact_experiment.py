from math import sqrt
from statistics import mean, stdev
import pytest
from pydantic import ValidationError
from contracts.analytics import ComparisonInput, ComparisonReport
from contracts.configuration import load_config
from backend.app.impact_comparison import arrival_schedule, simulate
from backend.app.impact_queue import Arrival, QueueExperiment


def engine(vehicles, **changes):
    return QueueExperiment(ComparisonInput(duration_seconds=300,warmup_seconds=0,replications=5,**changes),
        load_config(),[Arrival(i,at,d,m,k,.5) for i,(at,d,m,k) in enumerate(vehicles)],'ATCS')


def test_fractional_arrival_integrates_before_departure_and_includes_startup():
    points,_=engine([(.25,'U','straight','car')]).run()
    # Green at 2; startup 2; first headway 2.2 -> exit 6.2, wait 5.95.
    assert points[-1].cumulative_wait_vehicle_seconds == pytest.approx(5.95)
    assert points[-1].completed_average_wait_seconds == pytest.approx(5.95)
    assert points[-1].average_wait_seconds == pytest.approx(5.95)


def test_unfinished_vehicle_is_counted_in_mean_not_only_completed():
    points,_=engine([(.25,'U','straight','car'),(299.5,'U','straight','car')]).run()
    p=points[-1]
    assert p.completed_vehicles == 1 and p.queue_vehicles == 1
    assert p.cumulative_wait_vehicle_seconds == pytest.approx(6.45)
    assert p.average_wait_seconds == pytest.approx(3.225)
    assert p.completed_average_wait_seconds == pytest.approx(5.95)


def test_motorcycle_row_and_heavy_vehicle_headways_change_service_and_space():
    cars,_=engine([(1,'U','straight','car')]*3).run()
    motors,_=engine([(1,'U','straight','motorcycle')]*3).run()
    bus,_=engine([(1,'U','straight','bus')]).run()
    assert cars[-1].cumulative_wait_vehicle_seconds == pytest.approx(22.2)
    assert motors[-1].cumulative_wait_vehicle_seconds == pytest.approx(15.6)
    assert bus[-1].cumulative_wait_vehicle_seconds == pytest.approx(7.4)
    # B receives no green within 15 sec; evaluate untouched queue lengths.
    c,_=engine([(1,'B','straight','car')]*3).run()
    m,_=engine([(1,'B','straight','motorcycle')]*3).run()
    h,_=engine([(1,'B','straight','truck')]).run()
    assert c[1].maximum_lane_queue_meters == 19.5
    assert m[1].maximum_lane_queue_meters == 3
    assert h[1].maximum_lane_queue_meters == 13


def test_invisible_identity_cannot_leak_into_oldest_wait_and_actual_demand_is_identical():
    e=engine([(1,'T','straight','car')],detection_fraction=.1)
    e.queues[('T','straight')].append(e.arrivals[0]); e.now=40
    m=e.measurement().approaches['T']
    assert m.queue_count == 0 and m.oldest_wait_seconds == 0
    a=ComparisonInput(duration_seconds=300,replications=5)
    b=a.model_copy(update={'detection_fraction':.1})
    assert arrival_schedule(a) == arrival_schedule(b)


def test_warmup_counts_population_and_excludes_time_before_window():
    e=engine([(1,'T','straight','car')]); e.spec.warmup_seconds=60
    points,_=e.run()
    assert points[0].initial_queue_vehicles == 1 and points[0].arrivals == 0
    assert points[0].cumulative_wait_vehicle_seconds == 0
    # T green begins 2 + 85 + 3 + 2 = 92; startup/headway finish at 96.2.
    assert points[-1].average_wait_seconds == pytest.approx(96.2-60)
    assert all(p.queue_vehicles+p.completed_vehicles == p.initial_queue_vehicles+p.arrivals for p in points)


def test_class_fuel_and_co2_use_independent_gasoline_diesel_factors():
    e=engine([(1,'U','straight','car'),(1,'T','straight','truck'),(1,'B','straight','motorcycle')])
    points,_=e.run(); p=points[-1]; f=e.spec.factors
    seconds=p.queue_vehicle_seconds_by_class
    liters={k:s/3600*f.idle_liters_per_hour*e.spec.vehicle_factors[k].idle_multiplier for k,s in seconds.items()}
    assert sum(seconds.values()) == pytest.approx(p.cumulative_wait_vehicle_seconds,abs=.00001)
    assert p.idle_fuel_liters == pytest.approx(sum(liters.values()),abs=.000001)
    assert p.co2_kg == pytest.approx(sum(v*(f.diesel_co2_kg_per_liter if k in ('bus','truck') else f.co2_kg_per_liter) for k,v in liters.items()),abs=.000001)
    assert p.fuel_cost_rupiah == pytest.approx(sum(v*(f.diesel_fuel_rupiah_per_liter if k in ('bus','truck') else f.fuel_rupiah_per_liter) for k,v in liters.items()),abs=.0001)


def test_repetitions_use_all_paired_seeds_with_correct_student_interval_and_no_benefit_selection():
    report=simulate(ComparisonInput(duration_seconds=300,replications=5),load_config())
    assert [r.seed for r in report.runs] == [42,43,44,45,46]
    stat=next(m for m in report.metrics if m.key=='average_wait_seconds')
    differences=[r.atcs.average_wait_seconds-r.sigap.average_wait_seconds for r in report.runs]
    margin=2.776*stdev(differences)/sqrt(5)
    assert stat.improvement_mean == pytest.approx(mean(differences))
    assert stat.lower_95 == pytest.approx(mean(differences)-margin)
    assert stat.upper_95 == pytest.approx(mean(differences)+margin)
    assert report.atcs[-1] == report.runs[0].atcs
    assert report.emergency_status=='not_evaluated' and not report.baseline_field_verified
    altered=report.model_dump(); altered['runs'][1]['sigap']['completed_vehicles']+=1
    with pytest.raises(ValidationError): ComparisonReport.model_validate(altered)


def test_zero_baseline_means_no_percentage_or_invented_positive_interval():
    report=simulate(ComparisonInput(duration_seconds=300,replications=5,demand_per_minute=dict.fromkeys('UTSB',0)),load_config())
    assert all(m.result=='equal' and m.improvement_percent is None and m.lower_95==m.upper_95==0 for m in report.metrics)


def test_summary_only_replications_preserve_exact_results_without_sampling_overhead():
    spec=ComparisonInput(duration_seconds=300,replications=5)
    arrivals=arrival_schedule(spec)
    for strategy in ('ATCS','SIGAP'):
        full=QueueExperiment(spec,load_config(),arrivals,strategy).run()
        compact=QueueExperiment(spec,load_config(),arrivals,strategy,keep_series=False).run()
        assert len(compact[0]) == 2
        for key in ('average_wait_seconds','cumulative_wait_vehicle_seconds','idle_fuel_liters','completed_vehicles','queue_vehicles'):
            assert getattr(compact[0][-1],key) == pytest.approx(getattr(full[0][-1],key),abs=.00001)
        for direction in 'UTSB':
            a,b=compact[1][direction],full[1][direction]
            assert (a.participants,a.completed_vehicles,a.queue_vehicles)==(b.participants,b.completed_vehicles,b.queue_vehicles)
            assert a.average_wait_seconds==pytest.approx(b.average_wait_seconds,abs=.000001)


@pytest.mark.parametrize('changes',[{'class_mix':dict(motorcycle=0,car=0,bus=0,truck=0)}, {'turn_mix':dict(left=0,straight=0,right=0)}, {'demand_source':'zone_observation'}, {'replications':4}, {'warmup_seconds':901}])
def test_unusable_experiment_inputs_rejected(changes):
    with pytest.raises(ValidationError): ComparisonInput(**changes)
