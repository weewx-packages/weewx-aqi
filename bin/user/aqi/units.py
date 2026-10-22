# weewx-aqi
# Copyright 2018-2021 - Jonathan Koren <jonathan@jonathankoren.com>
# Modified 2026-10-22: fix concentration conversion, missing data and explicit EPA revisions.
# License: GPL 3

import weewx.units

from . import calculators

# molar masses (aka molecular mass) in units of grams per mole
MOLAR_MASSES = {
    'c': 12.011,    # carbon
    'o': 15.999,    # oxygen
    's': 32.06,     # sulfur
    'n': 14.007,    # nitrogen
    'h':  1.008     # hydrogen
}
MOLAR_MASSES.update({
    calculators.CO:  MOLAR_MASSES['c'] + MOLAR_MASSES['o'],
    calculators.NO2: MOLAR_MASSES['n'] + (2 * MOLAR_MASSES['o']),
    calculators.SO2: MOLAR_MASSES['s'] + (2 * MOLAR_MASSES['o']),
    calculators.O3:  3 * MOLAR_MASSES['o'],
    calculators.NH3: MOLAR_MASSES['n'] + (3 * MOLAR_MASSES['h']),
    calculators.PB:  207.2
})

GAS_CONSTANT = 8.31446  # in units of ((Pa m^3) / (K mol))
IDEAL_GAS_TEMP_IN_KELVIN = 273.15               # 0 centigrade
IDEAL_GAS_PRESSURE_IN_KILOPASCALS = 101.325     # 1 atmosphere

def convert_pollutant_units(pollutant, obs_value, obs_unit, required_unit, temp_in_kelvin, pressure_in_kilopascals):
    """Convert a pollutant concentration, accepting singular and legacy plural units.

    Args:
        pollutant (str): Pollutant key used by the standard.
        obs_value (int|float|None): Sensor concentration, or None for missing data.
        obs_unit (str): Source unit name.
        required_unit (str): Destination unit name.
        temp_in_kelvin (float|None): Sensor temperature for gas/mass conversion.
        pressure_in_kilopascals (float|None): Station pressure for gas/mass conversion.

    Returns:
        int|float|None: Converted concentration, or None for a missing observation.

    Raises:
        ValueError: Gas/mass conversion lacks positive temperature or pressure.
    """
    aliases = {'parts_per_million': 'part_per_million', 'parts_per_billion': 'part_per_billion',
               'ppm': 'part_per_million', 'ppb': 'part_per_billion'}
    obs_unit = aliases.get(obs_unit, obs_unit)
    required_unit = aliases.get(required_unit, required_unit)
    if obs_value is None or obs_unit == required_unit:
        return obs_value
    fraction_units = ('part_per_million', 'part_per_billion')
    mass_units = ('microgram_per_meter_cubed', 'milligram_per_meter_cubed')
    gas_to_mass = obs_unit in fraction_units and required_unit in mass_units
    mass_to_gas = obs_unit in mass_units and required_unit in fraction_units
    if gas_to_mass or mass_to_gas:
        if (temp_in_kelvin is None or pressure_in_kilopascals is None
                or temp_in_kelvin <= 0 or pressure_in_kilopascals <= 0):
            raise ValueError('Gas/mass conversion requires positive temperature and station pressure')
    if gas_to_mass:
        ppb = obs_value * 1000.0 if obs_unit == 'part_per_million' else obs_value
        concentration = ppb_to_microgram_per_meter_cubed(pollutant, ppb, temp_in_kelvin, pressure_in_kilopascals)
        return concentration / 1000.0 if required_unit == 'milligram_per_meter_cubed' else concentration
    if mass_to_gas:
        concentration = obs_value * 1000.0 if obs_unit == 'milligram_per_meter_cubed' else obs_value
        ppb = microgram_per_meter_cubed_to_ppb(pollutant, concentration, temp_in_kelvin, pressure_in_kilopascals)
        return ppb / 1000.0 if required_unit == 'part_per_million' else ppb
    return weewx.units.conversionDict[obs_unit][required_unit](obs_value)

def ppb_to_microgram_per_meter_cubed(pollutant, ppb, sensor_temp_in_kelvin=IDEAL_GAS_TEMP_IN_KELVIN, sensor_pressure_in_kilopascals=IDEAL_GAS_PRESSURE_IN_KILOPASCALS):
    '''Converts parts per billion to micrograms per cubic meters at temperature and pressure'''
    ugm3 = ppb * (sensor_pressure_in_kilopascals / GAS_CONSTANT) * MOLAR_MASSES[pollutant] / sensor_temp_in_kelvin
    return round(ugm3, 3)

def microgram_per_meter_cubed_to_ppb(pollutant, ug_per_m3, sensor_temp_in_kelvin=IDEAL_GAS_TEMP_IN_KELVIN, sensor_pressure_in_kilopascals=IDEAL_GAS_PRESSURE_IN_KILOPASCALS):
    '''Convert micrograms per cubic meter to parts per billion at temperature and pressure.'''
    ppb = (ug_per_m3 * sensor_temp_in_kelvin) / ((sensor_pressure_in_kilopascals / GAS_CONSTANT) * MOLAR_MASSES[pollutant])
    return round(ppb, 3)

# Define unit group for AQI columns
weewx.units.obs_group_dict['aqi_pm2_5'] = 'group_count'
weewx.units.obs_group_dict['aqi_pm10_0']  = 'group_count'
weewx.units.obs_group_dict['aqi_co']    = 'group_count'
weewx.units.obs_group_dict['aqi_no2']   = 'group_count'
weewx.units.obs_group_dict['aqi_so2']   = 'group_count'
weewx.units.obs_group_dict['aqi_o3']    = 'group_count'
weewx.units.obs_group_dict['aqi_nh3']   = 'group_count'
weewx.units.obs_group_dict['aqi_pb']    = 'group_count'

# define the units
#weewx.units.USUnits['group_count'] = 'count'
#weewx.units.MetricUnits['group_count'] = 'count'
#weewx.units.MetricWXUnits['group_count'] = 'count'
#weewx.units.default_unit_format_dict['air_quality_index'] = '%d'
#weewx.units.default_unit_label_dict['air_quality_index'] = '' # unitless

# unit conversion
if 'liter' not in weewx.units.conversionDict:
    weewx.units.conversionDict['liter'] = {}
weewx.units.conversionDict['liter']['meter_cubed'] = lambda x: x / 1000.0
weewx.units.conversionDict['meter_cubed'] = { 'liter': lambda x: x * 1000.0 }
weewx.units.conversionDict.setdefault('part_per_billion', {})['part_per_million'] = lambda x: x / 1000.0
weewx.units.conversionDict.setdefault('part_per_million', {})['part_per_billion'] = lambda x: x * 1000.0
weewx.units.conversionDict['microgram_per_meter_cubed'] = { 'milligram_per_meter_cubed': lambda x: x / 1000.0 }
weewx.units.conversionDict['milligram_per_meter_cubed'] = { 'microgram_per_meter_cubed': lambda x: x * 1000.0 }
