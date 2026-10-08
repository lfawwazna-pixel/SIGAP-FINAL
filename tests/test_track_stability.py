import pytest
from vision.stability import TrackStabilizer

def car(identity=1, x=.3, name='car'):
    return dict(track_id=identity,class_name=name,confidence=.9,bbox=[x,.3,x+.12,.45])

def test_missed_frames_hold_once_and_expire_without_refreshing_seen_time():
    s=TrackStabilizer()
    first=s.update([car()],0)[0]
    for at in (.2,.6,1.0,1.2):
        held=s.update([],at)
        assert len(held)==1 and held[0]['coasted'] and held[0]['track_id']==first['track_id']
    assert s.update([],1.21)==[]

def test_reassociation_keeps_identity_without_double_counting_adjacent_vehicles():
    s=TrackStabilizer()
    first=s.update([car(10),car(20,.55)],0)
    s.update([car(20,.55)],.2)
    result=s.update([car(30,.302),car(20,.55)],.4)
    assert len(result)==2
    assert [v['track_id'] for v in result]==[v['track_id'] for v in first]
    assert not any(v['coasted'] for v in result)

def test_camera_session_reset_and_edge_exit_never_keep_ghosts():
    a,b=TrackStabilizer(),TrackStabilizer()
    a.update([car()],0)
    assert b.update([],0)==[]
    edge=car(x=0); a=TrackStabilizer(); a.update([edge],0)
    assert a.update([],.2)==[]
    with pytest.raises(ValueError):
        a.update([],.2)

def test_different_classes_and_ambiguous_overlaps_are_not_reassociated():
    s=TrackStabilizer(); s.update([car()],0)
    output=s.update([car(2,name='ambulance')],.2)
    assert len(output)==2
    s=TrackStabilizer(); s.update([car(1),car(2,.31)],0)
    assert len(s.update([car(3,.305)],.2))==3


def test_near_identical_cross_class_boxes_keep_strongest_prediction_without_forcing_evp():
    from vision.stability import distinct_box_indices
    names=['car','motorcycle','bus','truck','ambulance','fire_truck']
    boxes=[[.44,.42,.58,.61],[.45,.425,.571,.611],[.61,.42,.74,.62]]
    assert distinct_box_indices(boxes,[0,4,0],[.42,.95,.8],names)==[1,2]
    # Uncertain EVP evidence must not override a stronger ordinary classification.
    assert distinct_box_indices(boxes,[0,4,0],[.95,.42,.8],names)==[0,2]
    # Adjacent/partly overlapping vehicles and different silhouettes stay separate.
    assert distinct_box_indices([[.3,.3,.42,.45],[.31,.3,.43,.45]], [0,0],[.9,.8],names)==[0,1]
    assert distinct_box_indices(boxes[:2],[0,1],[.9,.8],names)==[0,1]
