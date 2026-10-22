import json
from pathlib import Path

import pytest

from bin.user.aqi.ozone import ozone_nowcast, OzoneNowCast2019

FIXTURE = json.loads((Path(__file__).parent/'fixtures/epa_ozone_reference.json').read_text())


@pytest.mark.parametrize('case', FIXTURE['cases'], ids=lambda case: case['name'])
def test_matches_actual_epa_r_reference(case):
    value, method = ozone_nowcast(case['values'])
    assert method == case['expected_method']
    if case['expected_value'] is None:
        assert value is None
    else:
        assert value == pytest.approx(case['expected_value'], abs=1e-8)


def test_previous_hour_fallback():
    values = FIXTURE['cases'][0]['values'][:-1]+[None]
    assert ozone_nowcast(values, {1: 40.0}) == (40.0, 4)


def test_hourly_calculator_maps_prediction_to_primary_aqi_table():
    values = FIXTURE['cases'][0]['values']
    observations = [{'dateTime': (i+1)*3600, 'o3': value} for i,value in enumerate(values)]
    # Reference concentration 47.545 ppb truncates to 47 ppb, in the 0-54 band.
    assert OzoneNowCast2019(3600).calculate('o3','parts_per_billion',observations) == (44,0)


def test_model_through_actual_service_and_modern_weewx_ppm(tmp_path):
    from types import SimpleNamespace
    import weewx
    import weewx.manager
    from bin.user.aqi import service
    from tests.test_repairs import service_config
    config = service_config(tmp_path,'NowCast2019')
    config['DataBindings']['wx_binding']['schema']['o3'] = 'REAL'
    config['AqiService']['air_sensor'] = {'data_binding':'wx_binding','o3':'o3'}
    binder = weewx.manager.DBBinder(config)
    try:
        weather = binder.get_manager(data_binding='wx_binding',initialize=True)
        for i,value in enumerate(FIXTURE['cases'][0]['values']):
            weather.addRecord({'dateTime':(i+1)*3600,'usUnits':weewx.METRICWX,'interval':60,'o3':value/1000.0})
        extension = service.AqiService(SimpleNamespace(db_binder=binder,bind=lambda *args:None),config)
        extension.new_archive_record(SimpleNamespace(record={'dateTime':337*3600,'interval':60}))
        row = extension.aqi_dbm.getRecord(337*3600)
        assert row['aqi_standard'] == 13
        assert row['aqi_o3'] == 44
        assert row['aqi_o3_category'] == 0
    finally:
        binder.close()
