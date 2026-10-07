"""Map presence must remain legible without changing control measurements."""
from types import SimpleNamespace

import pytest

from backend.app.measurements import MAP_GEOMETRY, map_poses


def entries(count, lane):
    return [dict(track=SimpleNamespace(track_id=i+1, class_name='car'), lane=lane,
                 distance=(i*97)%625, stopped=False, passed=i%2 == 0)
            for i in range(count)]


def north_coordinates(vehicle):
    x, y = vehicle.x, vehicle.y
    for _ in range('UTSB'.index(vehicle.origin)):
        x, y = y, 2*MAP_GEOMETRY['center']-x
    return x, y


@pytest.mark.parametrize('direction', list('UTSB'))
@pytest.mark.parametrize('lane', ['outer', 'middle', 'inner'])
def test_full_bodies_fit_the_road_and_do_not_overlap_in_normal_traffic(direction, lane):
    vehicles = map_poses(direction, 'session', entries(12, lane))
    assert len(vehicles) == 12 and len({v.id for v in vehicles}) == 12
    centers = []
    for vehicle in vehicles:
        x, y = north_coordinates(vehicle)
        assert x == MAP_GEOMETRY['lane_centers'][lane]
        boundary = MAP_GEOMETRY['slip']['start'][1] if lane == 'outer' else MAP_GEOMETRY['stop_line']
        assert MAP_GEOMETRY['start'] < y-13.75 < y+13.75 < boundary
        centers.append(y)
    centers.sort()
    assert all(b-a > 27.5 for a, b in zip(centers, centers[1:]))


def test_box_jitter_and_input_order_cannot_swap_map_slots():
    initial = entries(6, 'middle')
    before = map_poses('U', 'session', initial)
    changed = [dict(entry, distance=625-entry['distance']) for entry in reversed(initial)]
    after = map_poses('U', 'session', changed)
    assert [(v.id, v.x, v.y) for v in after] == [(v.id, v.x, v.y) for v in before]
    # Real metadata is preserved even though drawing slots are schematic.
    assert {v.id: v.served for v in after} == {v.id: v.served for v in before}
    assert [v.distance_to_stop for v in after] != [v.distance_to_stop for v in before]


def test_crowding_and_departures_keep_all_ids_and_leave_no_stale_icons():
    crowded = entries(180, 'outer')
    before = map_poses('B', 'session', crowded)
    assert len(before) == 180 and len({(v.x, v.y) for v in before}) == 180
    assert all(-420 < v.x < 1220 and -420 < v.y < 1220 for v in before)
    after = map_poses('B', 'session', crowded[1::2])
    assert len(after) == 90 and {v.id for v in after} < {v.id for v in before}
    assert map_poses('B', 'session', []) == []
