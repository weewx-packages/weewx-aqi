import math
import importlib.util
import importlib.machinery
import sys
from pathlib import Path
from types import SimpleNamespace

import configobj
import pytest
import weewx
import weewx.manager

from bin.user.aqi import calculators, us, units, service, ca


@pytest.mark.parametrize('alias', ['parts_per_billion', 'part_per_billion', 'ppb'])
def test_mass_to_ozone_ppb(alias):
    assert units.convert_pollutant_units('o3', 214.139, 'microgram_per_meter_cubed',
        alias, 273.15, 101.325) == pytest.approx(100, abs=.001)


def test_ppm_is_one_thousand_ppb():
    assert units.convert_pollutant_units('co', 1.0, 'parts_per_million',
        'part_per_billion', None, None) == 1000.0
    assert units.convert_pollutant_units('co', 1000.0, 'part_per_billion',
        'parts_per_million', None, None) == 1.0


def test_no_meteorology_needed_for_particulates():
    assert units.convert_pollutant_units('pm2_5', None, 'microgram_per_meter_cubed',
        'microgram_per_meter_cubed', None, None) is None
    assert units.convert_pollutant_units('pm2_5', .012, 'milligram_per_meter_cubed',
        'microgram_per_meter_cubed', None, None) == 12.0


@pytest.mark.parametrize('concentration,expected', [(0,0), (9.0,50), (9.1,51), (35.4,100),
    (35.5,101), (55.4,150), (55.5,151), (125.4,200), (125.5,201), (225.4,300),
    (225.5,301), (325.4,500), (425.4,699)])
def test_epa_2024_primary_breakpoints(concentration, expected):
    # 40 CFR 58 Appendix G (2024), Table 2 and hazardous extrapolation footnote.
    observations = [{'dateTime': 86400-i*3600, 'pm2_5': concentration} for i in range(24)]
    value, category = us.AirQualityIndex2024(3600).calculate_aqi('pm2_5',
        'microgram_per_meter_cubed', observations)
    assert value == expected
    assert category == next(i for i, high in enumerate([50,100,150,200,300,math.inf]) if expected <= high)


def test_legacy_pm_table_remains_available():
    observations = [{'dateTime': 86400-i*3600, 'pm2_5': 9.0} for i in range(24)]
    assert us.AirQualityIndex(3600).calculate_aqi('pm2_5', 'microgram_per_meter_cubed', observations)[0] == 38


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1.0])
def test_invalid_observations_become_missing(value):
    observations = [{'dateTime': 86400-i*3600, 'pm2_5': value} for i in range(24)]
    with pytest.raises(ValueError):
        us.AirQualityIndex(3600).calculate_aqi('pm2_5', 'microgram_per_meter_cubed', observations)


@pytest.mark.parametrize('standard,concentration,expected', [
    ('AirQualityIndex', 900.0, None), ('AirQualityIndex2024', 425.4, 699),
    ('AirQualityIndex', 9.0, 38)])
def test_real_service_and_sqlite_missing_weather(tmp_path, standard, concentration, expected):
    config = service_config(tmp_path, standard)
    binder = weewx.manager.DBBinder(config)
    engine = SimpleNamespace(db_binder=binder, bind=lambda *args: None)
    try:
        weather = binder.get_manager(data_binding='wx_binding', initialize=True)
        for i in range(24):
            weather.addRecord({'dateTime': 86400-i*3600, 'usUnits':weewx.METRICWX,
                              'interval':60, 'pm2_5': concentration})
        extension = service.AqiService(engine, config)
        extension.new_archive_record(SimpleNamespace(record={'dateTime':90000,'interval':60}))
        row = extension.aqi_dbm.getRecord(90000)
        assert row is not None
        assert row['aqi_pm2_5'] == expected
        assert row['aqi_pm2_5_category'] is None if expected is None else row['aqi_pm2_5_category'] >= 0
    finally:
        binder.close()


def test_canadian_index_constructor_and_composite():
    standard = ca.AirQualityHealthIndex(3600)
    observations = [{'dateTime':10800-i*3600,'o3':30.0,'no2':10.0,'pm2_5':5.0} for i in range(3)]
    assert standard.calculate_composite_aqi(standard.get_pollutants(), observations) == (3, 2)


def test_nowcast_accepts_two_recent_hours_without_twelve_hour_warmup():
    observations = [{'dateTime':10800, 'pm2_5':100.0}, {'dateTime':7200, 'pm2_5':0.0}]
    assert us.NowCast2024(3600).calculate_aqi('pm2_5', 'microgram_per_meter_cubed', observations) == (159,3)


def test_nowcast_keeps_recent_missing_hours_in_window():
    observations = [{'dateTime':(i+1)*3600, 'pm2_5':9.0 if i<9 else None} for i in range(12)]
    with pytest.raises(ValueError, match='two valid hours'):
        us.NowCast2024(3600).calculate_aqi('pm2_5', 'microgram_per_meter_cubed', observations)


@pytest.mark.parametrize('standard', [us.AirQualityIndex, us.AirQualityIndex2024])
def test_so2_gap_between_hourly_and_daily_tables(standard):
    observations = [{'dateTime':86400-i*3600, 'so2':400.0 if i==0 else 0.0} for i in range(24)]
    assert standard(3600).calculate_aqi('so2', 'parts_per_billion', observations) == (200,3)


def test_modern_weewx_ppm_alias():
    assert units.convert_pollutant_units('o3', 0.080, 'ppm', 'parts_per_billion', None, None) == 80.0


def test_missing_weather_does_not_drop_particulate_samples():
    extension = service.AqiService.__new__(service.AqiService)
    rows = extension._join_sensor_results(iter([(10,16,9.0)]), ['dateTime','usUnits','pm2_5'],
        iter([]), ['dateTime','outTemp','pressure','weather_usUnits'], 300)
    assert rows == [{'dateTime':10,'usUnits':16,'pm2_5':9.0, 'outTemp':None,'pressure':None,'weather_usUnits':16}]


def test_new_epa_mode_rounds_half_up_while_legacy_stays_compatible():
    observations = [{'dateTime':86400-i*3600,'o3':80.0} for i in range(24)]
    assert us.AirQualityIndex2024(3600).calculate_aqi('o3','parts_per_billion', observations) == (133,2)
    assert us.AirQualityIndex(3600).calculate_aqi('o3','parts_per_billion', observations) == (132,2)


def test_backfill_reads_reordered_extended_schema_without_station_driver(tmp_path, monkeypatch):
    root = Path(__file__).parents[1]
    sys.path.insert(0, str(root/'bin'))
    loader = importlib.machinery.SourceFileLoader('aqi_backfill', str(root/'bin/aqi_backfill'))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    config = configobj.ConfigObj({'DataBindings':{'wx_binding':{'database':'weather',
        'manager':'weewx.manager.Manager','table_name':'custom_archive',
        'schema':{'dateTime':'INTEGER PRIMARY KEY','unrelated':'TEXT','interval':'INTEGER','usUnits':'INTEGER'}}},
        'Databases':{'weather':{'database_name':str(tmp_path/'backfill.sdb'),'driver':'weedb.sqlite'}}})
    with weewx.manager.open_manager_with_config(config,'wx_binding',initialize=True) as database:
        for stamp in [100,200,300]:
            database.addRecord({'dateTime':stamp,'interval':5,'usUnits':16,'unrelated':'do not use column position'})
    received = []
    class Receiver:
        def __init__(self, engine, config):
            pass
        def new_archive_record(self, event):
            received.append(event.record)
    monkeypatch.setattr(module.user.aqi.service,'AqiService',Receiver)
    assert module.backfill(config,100,300) == 2
    assert received == [{'dateTime':100,'interval':5},{'dateTime':200,'interval':5}]


def service_config(tmp_path, standard):
    config = configobj.ConfigObj({
        'StdArchive': {'archive_interval': 3600}, 'StdConvert': {'target_unit': 'METRICWX'},
        'AqiService': {'standard': {'standard': 'bin.user.aqi.us.'+standard, 'data_binding':'aqi_binding'},
                      'air_sensor': {'data_binding':'wx_binding', 'pm2_5':'pm2_5'}},
        'DataBindings': {'wx_binding': {'database':'weather', 'table_name':'archive',
            'manager':'weewx.manager.Manager', 'schema': {'dateTime':'INTEGER PRIMARY KEY',
            'usUnits':'INTEGER', 'interval':'INTEGER', 'pm2_5':'REAL', 'outTemp':'REAL',
            'barometer':'REAL', 'pressure':'REAL'}},
            'aqi_binding': {'database':'aqi', 'table_name':'archive', 'manager':'weewx.manager.Manager',
                           'schema':'bin.user.aqi.service.schema'}},
        'Databases': {'weather': {'database_name':str(tmp_path/'weather.sdb'), 'driver':'weedb.sqlite'},
                      'aqi': {'database_name':str(tmp_path/'aqi.sdb'), 'driver':'weedb.sqlite'}}})
    return config


@pytest.mark.parametrize('temperature,expected', [(0.0,100), (None,None)])
def test_service_custom_temperature_column_zero_and_null(tmp_path, temperature, expected):
    config = service_config(tmp_path,'AirQualityIndex2024')
    schema = config['DataBindings']['wx_binding']['schema']
    schema['extraTemp1'] = 'REAL'
    schema['no2'] = 'REAL'
    config['AqiService']['air_sensor'] = {'data_binding':'wx_binding','no2':'no2',
                                        'temp':'extraTemp1','pressure':'pressure'}
    binder = weewx.manager.DBBinder(config)
    try:
        weather = binder.get_manager(data_binding='wx_binding', initialize=True)
        for i in range(24):
            weather.addRecord({'dateTime':86400-i*3600,'usUnits':weewx.METRICWX,'interval':60,
                'extraTemp1':temperature,'outTemp':100.0,'pressure':1013.25,'no2':205.3})
        extension = service.AqiService(SimpleNamespace(db_binder=binder,bind=lambda *args:None),config)
        extension.new_archive_record(SimpleNamespace(record={'dateTime':90000,'interval':60}))
        row = extension.aqi_dbm.getRecord(90000)
        assert row['aqi_no2'] == expected
    finally:
        binder.close()


def test_sensor_frequency_override_and_invalid_interval():
    config = {'StdArchive':{'archive_interval':300}}
    assert service._observation_frequency(config,{'obs_frequency_in_sec':'60'}) == 60
    assert service._observation_frequency(config,{}) == 300
    with pytest.raises(ValueError, match='positive'):
        service._observation_frequency(config,{'obs_frequency_in_sec':0})


def test_canadian_composite_through_actual_service(tmp_path):
    config = service_config(tmp_path,'AirQualityIndex2024')
    config['AqiService']['standard']['standard'] = 'bin.user.aqi.ca.AirQualityHealthIndex'
    config['DataBindings']['wx_binding']['schema'].update({'o3':'REAL','no2':'REAL'})
    config['AqiService']['air_sensor'] = {'data_binding':'wx_binding','o3':'o3',
        'no2':'no2','pm2_5':'pm2_5','temp':'outTemp','pressure':'pressure'}
    binder = weewx.manager.DBBinder(config)
    try:
        weather = binder.get_manager(data_binding='wx_binding', initialize=True)
        for i in range(3):
            weather.addRecord({'dateTime':86400-i*3600,'usUnits':weewx.METRICWX,'interval':60,
                'outTemp':0.0,'pressure':1013.25,'no2':20.53,'o3':0.030,'pm2_5':5.0})
        extension = service.AqiService(SimpleNamespace(db_binder=binder,bind=lambda *args:None),config)
        extension.new_archive_record(SimpleNamespace(record={'dateTime':90000,'interval':60}))
        row = extension.aqi_dbm.getRecord(90000)
        assert row['aqi_composite'] == 3
        assert row['aqi_composite_category'] == 2
    finally:
        binder.close()


def test_australian_module_and_existing_particulate_classes():
    from bin.user.aqi import au
    standard = au.AirQualityIndex(3600)
    rows = [{'dateTime':86400-i*3600,'pm2_5':25.0} for i in range(24)]
    assert standard.calculate_aqi('pm2_5','microgram_per_meter_cubed',rows) == (100,3)
    interim = au.InterimWebReportingParticulateIndex(3600)
    assert interim.calculate_aqi('pm2_5','microgram_per_meter_cubed',
        [{'dateTime':3600,'pm2_5':62.1}]) == (100,3)


def test_all_installed_python_modules_compile():
    import py_compile
    root = Path(__file__).parents[1]
    for path in (root/'bin').rglob('*.py'):
        py_compile.compile(str(path), doraise=True)
