# weewx-aqi
# Copyright 2018-2021 - Jonathan Koren <jonathan@jonathankoren.com>
# Modified 2026-10-22: fix concentration conversion, missing data and explicit EPA revisions.
# License: GPL 3

import operator
import syslog

from . import calculators
from . import standards

# Colors defiend by https://www3.epa.gov/airnow/aqi-technical-assistance-document-may2016.pdf
GREEN = '00e400'
YELLOW = 'ffff00'
ORANGE = 'ff7e00'
RED = 'ff0000'
PURPLE = '8f3f97'
MAROON = '7e0023'

class AirQualityIndex(standards.AqiStandards):
    '''Calculates the air quality index (AQI) as defined by the US EPA in
    https://www3.epa.gov/airnow/aqi-technical-assistance-document-may2016.pdf

    Note that AQIs > 500 are explicitly undefined, and should be reported as,
    "Beyond the AQI".'''
    def __init__(self, obs_frequency_in_sec):
        super(AirQualityIndex, self).__init__(
            [GREEN, YELLOW, ORANGE, RED, PURPLE, MAROON],
            ['Good', 'Moderate', 'Unhealthy for Sensitive Groups', 'Unhealthy', 'Very Unhealthy', 'Hazardous'],
            standards.US_AQI_GUID)

        # US doesn't specify number of observations required. lets go with 75% since that's the UK's standard
        self.calculators[calculators.PM2_5] = calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_1,
            mean_cleaner=calculators.TRUNCATE_TO_1,
            unit='microgram_per_meter_cubed',
            duration_in_secs=24 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,   0.0,  12.0) \
            .add_breakpoint( 51, 100,  12.1,  35.4) \
            .add_breakpoint(101, 150,  35.5,  55.4) \
            .add_breakpoint(151, 200,  55.5, 150.4) \
            .add_breakpoint(201, 300, 150.5, 250.4) \
            .add_breakpoint(301, 500, 250.5, 500.4)

        self.calculators[calculators.PM10_0] = calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            unit='microgram_per_meter_cubed',
            duration_in_secs=24 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,   0,  54) \
            .add_breakpoint( 51, 100,  55, 154) \
            .add_breakpoint(101, 150, 155, 254) \
            .add_breakpoint(151, 200, 255, 354) \
            .add_breakpoint(201, 300, 355, 424) \
            .add_breakpoint(301, 500, 425, 604)

        self.calculators[calculators.CO] = calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_1,
            mean_cleaner=calculators.TRUNCATE_TO_1,
            unit='parts_per_million',
            duration_in_secs=8 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,  0.0,  4.4) \
            .add_breakpoint( 51, 100,  4.5,  9.4) \
            .add_breakpoint(101, 150,  9.5, 12.4) \
            .add_breakpoint(151, 200, 12.5, 15.4) \
            .add_breakpoint(201, 300, 15.5, 30.4) \
            .add_breakpoint(301, 500, 30.5, 50.4)

        self.calculators[calculators.NO2] = calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            unit='parts_per_billion',
            duration_in_secs=1 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,    0,   53) \
            .add_breakpoint( 51, 100,   54,  100) \
            .add_breakpoint(101, 150,  101,  360) \
            .add_breakpoint(151, 200,  361,  649) \
            .add_breakpoint(201, 300,  650, 1249) \
            .add_breakpoint(301, 500, 1250, 2049)

        # Per https://www3.epa.gov/airnow/aqi-technical-assistance-document-may2016.pdf :
        # "How do I calculate aqi values for SO2? [...] If you have a daily max 1-hour.HOUR
        # SO2 concentration below 305 ppb, then use the breakpoints in Table 2 to
        # calculate theaqi value. If you have a 24-hour average SO2 concentration
        # greater than or equal to 305 ppb, then use the breakpoints in Table 2 to
        # calculate theaqi value.  If you have a 24-hour value in this range, it will
        # always result in a higher aqi value than a 1-hour value would. On rare occasions,
        # you could have a day where the daily max 1-hour concentration is at or above
        # 305 ppb but when you try to use the 24-hour average to calculate theaqi
        # value, you find that the 24-hour concentration is not above 305 ppb. If this
        # happens, use 200 for the lower and upper aqi breakpoints (ILo and IHi) in
        # Equation 1 to calculate theaqi value based on the daily max 1-hour value.
        # This effectively fixes the aqi value at 200 exactly, which ensures that you
        # get the highest possible aqi value associated with your 1-hour concentration
        # on such days."
        #
        # In this implmentation, the AqiTable will throw a ValueError saying
        # the AQI could not be calculated. In this case, the caller will need
        # check if the 1-hour average is >= 305 and the 24-hour average is < 305,
        # then return an AQi of exactly 200.
        self.calculators[calculators.SO2] = calculators.CalculatorCollection()
        self.calculators[calculators.SO2].add_calculator(calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            unit='parts_per_billion',
            duration_in_secs=1 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,   0,  35) \
            .add_breakpoint( 51, 100,  36,  75) \
            .add_breakpoint(101, 150,  76, 185) \
            .add_breakpoint(151, 200, 186, 304))
        self.calculators[calculators.SO2].add_calculator(calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            unit='parts_per_billion',
            duration_in_secs=24 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec,
            bp_index_offset=4) \
            .add_breakpoint(201, 300, 305,  604) \
            .add_breakpoint(301, 500, 605, 1004))

        # Alas, there are two overlapping tables for ozone.
        # Per https://www3.epa.gov/airnow/aqi-technical-assistance-document-may2016.pdf :
        # "Areas are generally required to report the aqi based on 8-hour ozone
        # values.  However, there are a small number of areas where anaqi based on
        # 1-hour ozone values would be more precautionary.  In these cases, in
        # addition to calculating the 8-hour ozone index value, the 1-hour ozone
        # value may be calculated, and the maximum of the two values reported.""
        #
        # Furthermore, "8-hour O3 values do not define higher aqi values (>= 301).
        # aqi values of 301 or higher are calculated with 1-hour O3 concentrations."
        #
        # Later, "How do I use both ozone 1-hour and 8-hour values? You must
        # calculate the 8-hour values, and you may also calculate the 1-hour values.
        # If you calculate both, you must report the higheraqi value."
        #
        # "What do I do with concentrations for pollutants that have blank places
        # in the table for Breakpoints for the aqi? Disregard those numbers.
        # Suppose you had a 1-hour ozone value of 0.104 ppm and an 8-hour ozone
        # value of 0.078 ppm.  First you disregard the 1-hour ozone value because
        # it is less than 0.125 ppm.  Then you calculate the index for the 8-hour
        # ozone value as before.
        self.calculators[calculators.O3] = calculators.CalculatorCollection()
        self.calculators[calculators.O3].add_calculator(calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            unit='parts_per_billion',
            duration_in_secs=8 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,   0,  54) \
            .add_breakpoint( 51, 100,  55,  70) \
            .add_breakpoint(101, 150,  71,  85) \
            .add_breakpoint(151, 200,  86, 105) \
            .add_breakpoint(201, 300, 106, 200))
        self.calculators[calculators.O3].add_calculator(calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            unit='parts_per_billion',
            duration_in_secs=1 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec,
            bp_index_offset=2) \
            .add_breakpoint(101, 150, 125, 164) \
            .add_breakpoint(151, 200, 165, 204) \
            .add_breakpoint(201, 300, 205, 404) \
            .add_breakpoint(301, 500, 405, 604))

    def calculate_aqi(self, pollutant, observation_unit, observations):
        calculator = self.calculators[pollutant]
        try:
            aqi_value = calculator.calculate(pollutant, observation_unit, observations)
            return aqi_value
        except (IndexError, ValueError) as error:
            if pollutant != calculators.SO2 or observation_unit != calculator.unit:
                raise
            means = []
            for table in calculator.calculators:
                mean = calculators.ArithmeticMean(unit=table.unit,
                    duration_in_secs=table.duration_in_secs,
                    obs_frequency_in_sec=table.obs_frequency_in_sec,
                    data_cleaner=table.data_cleaner,
                    required_observation_ratio=table.required_observation_ratio)
                try:
                    means.append(mean.calculate(pollutant, observation_unit, observations)[0])
                except ValueError:
                    raise error
            # EPA's special case when the 1-hour value is high but 24-hour is low.
            if means[0] >= 305 and means[1] < 305:
                return (200, 3)
            raise error

def nowcast_pm_mean(observations, obs_frequency_in_sec, required_observation_ratio, min_hours):
    '''Calculates the NowCast weighted mean for a set of observations. Each
    hourly average requires at least required_observation_ratio of the possible readings. '''
    hourly_sums = [0.0] * 12
    hourly_samples = [0.0] * 12

    # calculate hourly means
    start_time = observations[0][0]
    for obs in observations:
        index = int((start_time - obs[0]) / calculators.HOUR)
        hourly_samples[index] = hourly_samples[index] + 1
        hourly_sums[index] = hourly_sums[index] + obs[1]

    # validate the samples, and calculate the data range
    required = (calculators.HOUR / obs_frequency_in_sec) * required_observation_ratio
    hourly_means = [calculators.TRUNCATE_TO_1(total / count) if count >= required else None
                    for total, count in zip(hourly_sums, hourly_samples)]
    valid_means = [value for value in hourly_means if value is not None]
    if not valid_means:
        raise ValueError('NowCast has no valid hourly means')
    max_obs = max(valid_means)
    min_obs = min(valid_means)

    # check if we have enough recent data
    missing = 0
    for i in range(min_hours):
        if hourly_means[i] is None:
            missing = missing + 1
    if missing >= round(min_hours * 0.667):
        raise ValueError('NowCast AQI could not be calculated for the observations. Too many missing. Missing %d, which meets or exceeding the limit of %d' % (missing, round(min_hours * 0.667)))

    # determine the weights
    weight_factor = 1.0
    if max_obs > 0:
        weight_factor = 1.0 - ((max_obs - min_obs) / float(max_obs))
    if weight_factor < 0.5:
        weight_factor = 0.5

    # calcualte the weighted average
    numerator = 0.0
    denominator = 0.0
    for i, value in enumerate(hourly_means):
        if value is None:
            continue
        sample_weight = weight_factor ** i
        numerator = numerator + (value * sample_weight)
        denominator = denominator + sample_weight
    return numerator / float(denominator)


def nowcast_o3_mean(observations, obs_frequency_in_sec, required_observation_ratio, min_hours):
    # We're using the old (pre-2019) method, instead of the partial least squares
    # and decision tree stuff outlined in
    # https://raw.githubusercontent.com/USEPA/O3-Nowcast/master/WhitePaper.pdf
    return nowcast_pm_mean(observations, obs_frequency_in_sec, required_observation_ratio, min_hours)

class NowCast(standards.AqiStandards):
    '''Calculates the US EPA NowCast Air Quality Index (AQI) as defined by the
    US EPA in https://www3.epa.gov/airnow/aqi-technical-assistance-document-may2016.pdf
    and https://www3.epa.gov/airnow/ani/pm25_aqi_reporting_nowcast_overview.pdf .
    NowCast is meant to provide more realtime air quality measurements by
    using shorter averaging times along with weighting the averages so that
    more recent measurements have more importantce. The AQI calculation tables
    are identical to the traditional AQI tables.

    Note that AQIs > 500 are explicitly undefined, and should be reported as,
    "Beyond the AQI".'''
    def __init__(self, obs_frequency_in_sec):
        super(NowCast, self).__init__(
            [GREEN, YELLOW, ORANGE, RED, PURPLE, MAROON],
            ['Good', 'Moderate', 'Unhealthy for Sensitive Groups', 'Unhealthy', 'Very Unhealthy', 'Hazardous'],
            standards.US_NOWCAST_GUID)

        # US doesn't specify number of observations required. lets go with 75% since that's the UK's standard
        self.calculators[calculators.PM2_5] = calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_1,
            mean_cleaner=calculators.TRUNCATE_TO_1,
            mean_calculator=lambda obs: nowcast_pm_mean(obs, obs_frequency_in_sec, 0.75, 3),
            unit='microgram_per_meter_cubed',
            duration_in_secs=12 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,   0.0,  12.0) \
            .add_breakpoint( 51, 100,  12.1,  35.4) \
            .add_breakpoint(101, 150,  35.5,  55.4) \
            .add_breakpoint(151, 200,  55.5, 150.4) \
            .add_breakpoint(201, 300, 150.5, 250.4) \
            .add_breakpoint(301, 500, 250.5, 500.4)

        self.calculators[calculators.PM10_0] = calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            mean_calculator=lambda obs: nowcast_pm_mean(obs, obs_frequency_in_sec, 0.75, 3),
            unit='microgram_per_meter_cubed',
            duration_in_secs=12 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,   0,  54) \
            .add_breakpoint( 51, 100,  55, 154) \
            .add_breakpoint(101, 150, 155, 254) \
            .add_breakpoint(151, 200, 255, 354) \
            .add_breakpoint(201, 300, 355, 424) \
            .add_breakpoint(301, 500, 425, 604)

        self.calculators[calculators.O3] = calculators.CalculatorCollection()
        self.calculators[calculators.O3].add_calculator(calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            mean_calculator=lambda obs: nowcast_o3_mean(obs, obs_frequency_in_sec, 0.75, 1),
            unit='parts_per_billion',
            duration_in_secs=1 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec) \
            .add_breakpoint(  0,  50,   0,  54) \
            .add_breakpoint( 51, 100,  55,  70) \
            .add_breakpoint(101, 150,  71,  85) \
            .add_breakpoint(151, 200,  86, 105) \
            .add_breakpoint(201, 300, 106, 200))
        self.calculators[calculators.O3].add_calculator(calculators.BreakpointTable(
            data_cleaner=calculators.TRUNCATE_TO_0,
            mean_cleaner=calculators.TRUNCATE_TO_0,
            mean_calculator=lambda obs: nowcast_o3_mean(obs, obs_frequency_in_sec, 0.75, 1),
            unit='parts_per_billion',
            duration_in_secs=8 * calculators.HOUR,
            obs_frequency_in_sec=obs_frequency_in_sec,
            bp_index_offset=2) \
            .add_breakpoint(101, 150, 125, 164) \
            .add_breakpoint(151, 200, 165, 204) \
            .add_breakpoint(201, 300, 205, 404) \
            .add_breakpoint(301, 500, 405, 604))


class AirQualityIndex2024(AirQualityIndex):
    """Use EPA's May 2024 PM2.5 breakpoints and hazardous extrapolation.

    Legacy AirQualityIndex remains available for historical comparisons.
    """
    def __init__(self, obs_frequency_in_sec):
        super(AirQualityIndex2024, self).__init__(obs_frequency_in_sec)
        self.guid = standards.US_AQI_2024_GUID
        self.calculators[calculators.PM2_5] = _pm25_2024_table(obs_frequency_in_sec)
        for calculator in self.calculators.values():
            tables = calculator.calculators if isinstance(calculator, calculators.CalculatorCollection) else [calculator]
            for table in tables:
                # Ozone's 8-hour table ends at AQI 300, not a hazardous interval.
                table.extend_above = table.breakpoints[-1]['high_aqi'] == 500
                for breakpoint in table.breakpoints:
                    breakpoint['function'] = calculators.epa_linear_interpolate


class NowCast2024(NowCast):
    """Use 2024 PM2.5 breakpoints and EPA particulate completeness rules.

    Ozone retains the explicitly documented legacy method.
    """
    def __init__(self, obs_frequency_in_sec):
        super(NowCast2024, self).__init__(obs_frequency_in_sec)
        self.guid = standards.US_NOWCAST_2024_GUID
        table = _pm25_2024_table(obs_frequency_in_sec)
        table.duration_in_secs = 12 * calculators.HOUR
        table.mean_calculator = lambda obs: nowcast_pm_mean(obs, obs_frequency_in_sec, 0.75, 3)
        self.calculators[calculators.PM2_5] = ParticulateNowCast(table, obs_frequency_in_sec)
        self.calculators[calculators.PM10_0].extend_above = True
        for breakpoint in self.calculators[calculators.PM10_0].breakpoints:
            breakpoint['function'] = calculators.epa_linear_interpolate
        self.calculators[calculators.PM10_0] = ParticulateNowCast(
            self.calculators[calculators.PM10_0], obs_frequency_in_sec)


def _pm25_2024_table(obs_frequency_in_sec):
    """Create the PM2.5 table in 40 CFR 58 Appendix G, Table 2.

    Args:
        obs_frequency_in_sec (int): Seconds between archived sensor observations.

    Returns:
        calculators.BreakpointTable: May 2024 PM2.5 thresholds with extrapolation.
    """
    table = calculators.BreakpointTable(
        data_cleaner=calculators.IDENTITY, mean_cleaner=calculators.TRUNCATE_TO_1,
        unit='microgram_per_meter_cubed', duration_in_secs=24 * calculators.HOUR,
        obs_frequency_in_sec=obs_frequency_in_sec, extend_above=True)
    for low_aqi, high_aqi, low, high in [
        (0, 50, 0.0, 9.0), (51, 100, 9.1, 35.4), (101, 150, 35.5, 55.4),
        (151, 200, 55.5, 125.4), (201, 300, 125.5, 225.4), (301, 500, 225.5, 325.4)]:
        table.add_breakpoint(low_aqi, high_aqi, low, high, calculators.epa_linear_interpolate)
    return table


class ParticulateNowCast(calculators.AqiCalculator):
    """Apply the EPA two-of-three-hour rule before mapping the weighted mean."""

    def __init__(self, table, obs_frequency_in_sec):
        super(ParticulateNowCast, self).__init__(unit=table.unit,
            duration_in_secs=12*calculators.HOUR, obs_frequency_in_sec=obs_frequency_in_sec)
        self.table = table

    def calculate(self, pollutant, observation_unit, observations):
        import math
        if observation_unit != self.unit or not observations:
            raise ValueError('NowCast needs observations in %s' % self.unit)
        latest_hour = (max(row['dateTime'] for row in observations)-1)//calculators.HOUR
        hours = [[] for i in range(12)]
        for row in observations:
            offset = latest_hour-(row['dateTime']-1)//calculators.HOUR
            value = row.get(pollutant)
            if 0 <= offset < 12 and value is not None and math.isfinite(value) and value >= 0:
                hours[offset].append(value)
        needed = calculators.HOUR/self.obs_frequency_in_sec*0.75
        means = [math.fsum(hour)/len(hour) if len(hour) >= needed else None for hour in hours]
        if sum(value is not None for value in means[:3]) < 2:
            raise ValueError('NowCast needs two valid hours among the latest three')
        available = [value for value in means if value is not None]
        maximum = max(available)
        weight = max(0.5, min(available)/maximum) if maximum > 0 else 1.0
        numerator = math.fsum(value*weight**i for i,value in enumerate(means) if value is not None)
        denominator = math.fsum(weight**i for i,value in enumerate(means) if value is not None)
        return self.table._calculate_index_from_mean(self.table.mean_cleaner(numerator/denominator))

    def _calculate_index_from_mean(self, mean):
        return self.table._calculate_index_from_mean(mean)


class NowCast2019(NowCast2024):
    """Combine EPA 2019 ozone prediction with 2024 particulate breakpoints."""

    def __init__(self, obs_frequency_in_sec):
        super(NowCast2019, self).__init__(obs_frequency_in_sec)
        from .ozone import OzoneNowCast2019
        self.calculators[calculators.O3] = OzoneNowCast2019(obs_frequency_in_sec)
        self.guid = standards.US_NOWCAST_2019_GUID
