# weewx-aqi
# Copyright 2018-2021 - Jonathan Koren <jonathan@jonathankoren.com>
# Modified 2026-10-22: fix concentration conversion, missing data and explicit EPA revisions.
# License: GPL 3

from abc import ABCMeta, abstractmethod
import operator
import math
import syslog


# number of seconds
MINUTE = 60
HOUR = 3600
DAY = 86400

# data cleaning functions
IDENTITY = lambda x: x
ROUND_TO_0 = lambda x: round(x)
ROUND_TO_1 = lambda x: round(x, 1)
ROUND_TO_2 = lambda x: round(x, 2)
ROUND_TO_3 = lambda x: round(x, 3)
TRUNCATE_TO_0 = lambda x: int(x)
TRUNCATE_TO_1 = lambda x: int(x * 10) / 10.0

# polution constants
PM2_5 = 'pm2_5'
PM10_0 = 'pm10_0'
CO = 'co'
NO2 = 'no2'
SO2 = 'so2'
O3 = 'o3'
NH3 = 'nh3'
PB = 'pb'

def get_last_valid_index(observations, duration_in_secs):
    '''Returns index into observations of the observation that is the
    closest, but not earlier than the earliest valid timestamp.'''
    if (len(observations) == 0) or (len(observations[0]) == 0):
        raise ValueError('no observations')

    first_invalid_timestamp = observations[0][0] - duration_in_secs
    best_delta = None
    best_index = None
    start = 0
    end = len(observations)

    while start < end:
        mid = int((end - start) / 2) + start
        delta = observations[mid][0] - first_invalid_timestamp;
        if delta < 0:
            # observation is too early
            end = mid
        elif delta == 0:
            # We found the first invalid index, back up one
            best_index = mid - 1
            break
        else:
            # observation might be valid
            if best_delta is None or best_delta > delta:
                best_delta = delta
                best_index = mid
                start = mid + 1
            else:
                # worst delta, go to the front
                end = mid
    if best_index is None:
        raise ValueError('all observations are outside the valid range')

    return best_index

def validate_number_of_observations(observations, duration_in_secs, obs_frequency_in_sec, required_observation_ratio):
    '''Checks that there are enough observations to calculate a metric. If not
    enough observations are present, throws ValueError.'''
    num_required = (duration_in_secs / obs_frequency_in_sec) * required_observation_ratio
    if len(observations) < num_required:
        raise ValueError('Not enough observations wanted %d, but got %d' % (num_required, len(observations)))

def linear_interpolate(breakpoint, obs_mean):
    numerator = (obs_mean - breakpoint['low_obs']) * (breakpoint['high_aqi'] - breakpoint['low_aqi'])
    denominator = breakpoint['high_obs'] - breakpoint['low_obs']
    return int(round((numerator / float(denominator)) + breakpoint['low_aqi']))

def epa_linear_interpolate(breakpoint, obs_mean):
    """Interpolate an EPA AQI, rounding half values upward.

    Args:
        breakpoint (dict): Concentration and AQI bounds.
        obs_mean (float): Truncated pollutant concentration.

    Returns:
        int: AQI rounded to the nearest integer.
    """
    value = ((obs_mean-breakpoint['low_obs'])*
             (breakpoint['high_aqi']-breakpoint['low_aqi'])/
             (breakpoint['high_obs']-breakpoint['low_obs'])+breakpoint['low_aqi'])
    return int(math.floor(value+0.5))

def arithmetic_mean(observations):
    '''Calculates the arithmetic mean from a set of observations.
    `observations` is reverse chronologically sorted array timestamped
    readings. Each reading is a pair, with epoch seconds first, followed by
    the measurment.'''
    return math.fsum(obs[1] for obs in observations) / float(len(observations))

class AqiCalculator(metaclass=ABCMeta):
    def __init__(self, **kwargs):
        '''Creates a new AqiCalculator. Takes the following keyword arguments:
            data_cleaner
                function to be applied to each observation prior to calculation
                DEFAULT: IDENTITY

            mean_cleaner
                function to be applied after the mean calculation
                DEFAULT: IDENTITY

            mean_calculator
                Function that returns the mean observation from a list of samples
                DEFAULT: arithmetic_mean

            unit (REQUIRED)
                units the observations are in

            duration_in_secs (REQUIRED)
                number of seconds of observations the AQI is calculated over

            obs_frequency_in_sec (REQUIRED)
                expected number of seconds between observations

            required_observation_ratio
                ratio of observations made to total possible observations
                that must be present in order to calculate the AQI
                DEFAULT: 0.75
        '''
        self.data_cleaner = kwargs.get('data_cleaner', IDENTITY)
        self.mean_cleaner = kwargs.get('mean_cleaner', IDENTITY)
        self.mean_calculator = kwargs.get('mean_calculator', arithmetic_mean)
        self.unit = kwargs['unit']
        self.obs_frequency_in_sec = kwargs['obs_frequency_in_sec']
        self.required_observation_ratio = kwargs.get('required_observation_ratio', 0.75)
        self.duration_in_secs = kwargs['duration_in_secs']

    def max_duration(self):
        '''Returns the maximum duration window for the calculator.'''
        return self.duration_in_secs

    def calculate(self, pollutant, observation_unit, observations):
        '''Returns the AQI index for the set of observations.
        Observations are recorded as an array of maps containing keys `dateTime`
        (containing epoch seconds for the observation) and the key specified by
        `pollutant` with a value recorded in units of `observation_unit`.
        Returns a pair containing the AQI and the index to the AQI category.

        NOTE: It is imperative that implementations verify the units of
        observations (performing conversions if appropriate), prior calculation.
        Raises ValueError if the observations are somehow invalid (e.g. wrong
        units, wrong time range, too many missing values, etc.).'''
        if observation_unit != self.unit:
            raise ValueError('inappropriate units, expected %s, but got %s' % (self.unit, observation_unit))

        # clean the data
        observations = sorted(observations, key=operator.itemgetter('dateTime'), reverse=True)

        clean_observations = []
        for i in range(len(observations)):
            value = observations[i].get(pollutant)
            if value is None or not math.isfinite(value) or value < 0:
                continue
            try:
                clean_observations.append((observations[i]['dateTime'], self.data_cleaner(observations[i][pollutant])))
            except TypeError as e:
                syslog.syslog(syslog.LOG_WARNING, "%s at %d threw exception %s" % (pollutant, observations[i]['dateTime'], str(e)))
        observations = clean_observations

        # validate observations
        last_valid_index = get_last_valid_index(observations, self.duration_in_secs)
        observations = observations[:last_valid_index + 1]
        validate_number_of_observations(observations,
            self.duration_in_secs,
            self.obs_frequency_in_sec,
            self.required_observation_ratio)

        # calculate the mean observation
        obs_mean = self.mean_cleaner(self.mean_calculator(observations))

        # map the mean to an AQI value
        return self._calculate_index_from_mean(obs_mean)

    @abstractmethod
    def _calculate_index_from_mean(self, mean):
        '''Performs the final calculation of the AQI after all data validation
        and cleaning has been performed.

        This is a private function to be called from calculate().'''
        raise NotImplementedError()

class CalculatorCollection(AqiCalculator):
    '''Used when multiple AqiCalculators are used for the single pollutant in
    a single standard.

    This is not a common case.'''
    def __init__(self, **kwargs):
        '''Creates a new CalculatorCollection'''
        # we don't need anything here, we're just implementing the interface.
        # BreakpointTables do all the work.
        super(CalculatorCollection, self).__init__(unit=None, duration_in_secs=None, obs_frequency_in_sec=None)
        self.calculators = []

    def add_calculator(self, calculator):
        '''Adds an AqiCalculator to the CalculatorCollection'''
        self.calculators.append(calculator)
        self.unit = self.calculators[0].unit
        return calculator

    def max_duration(self):
        max_dur = 0
        for t in self.calculators:
            if t.max_duration() > max_dur:
                max_dur = t.max_duration()
        return max_dur

    def calculate(self, pollutant, observation_unit, observations):
        '''Returns a calculation by combining the results of the subcalulators.
        Any subcalculator that fails to return a result is skipped. The maximum
        score from multiple results is returned.'''
        aqi_result = None
        for calculator in self.calculators:
            try:
                res = calculator.calculate(pollutant, observation_unit, observations)
                if (aqi_result is None) or (res[0] > aqi_result[0]):
                    aqi_result = res
            except IndexError:
                # off scale
                pass
            except ValueError:
                # not enough observations
                pass
        if aqi_result != None:
            return aqi_result
        else:
            raise ValueError('AQI could not be calculated for the observations')

    def _calculate_index_from_mean(self, mean):
        raise NotImplementedError()

class BreakpointTable(AqiCalculator):
    '''Calculates an air quality index (AQI) from a table. Each entry in the
    table contains a mapping of a rage of AQI values to a range of pollutant
    concentrations. The specific AQI value is determined by a linear
    interpolation of pollutant concentration to AQI value defined for the
    range.'''
    def __init__(self, **kwargs):
        '''Creates a new breakpoint table that is valid for observations in
        the specified time range. This table is initially empty.

        Additional kwargs:
            bp_index_offset
                First entry of this BreakpointTable corresponds to this AQI index
                DEFAULT: 0
        '''
        super(BreakpointTable, self).__init__(**kwargs)
        params = {
            'bp_index_offset': 0,
        }
        params.update(kwargs)

        self.bp_index_offset = params['bp_index_offset']
        self.extend_above = kwargs.get('extend_above', False)
        self.breakpoints = []

    def add_breakpoint(self, low_aqi, high_aqi, low_obs, high_obs, function=linear_interpolate):
        '''Adds an entry to the table, mapping a range of AQIs to a range of observations.'''
        self.breakpoints.append({
            'low_aqi':  low_aqi,
            'high_aqi': high_aqi,
            'low_obs':  low_obs,
            'high_obs': high_obs,
            'function': function,
        })
        self.breakpoints = sorted(self.breakpoints, key=operator.itemgetter('low_obs'))
        return self

    def _calculate_index_from_mean(self, obs_mean):
        for bp_index in range(len(self.breakpoints)):
            breakpoint = self.breakpoints[bp_index]
            if breakpoint['low_obs'] <= obs_mean and obs_mean <= breakpoint['high_obs']:
                return (breakpoint['function'](breakpoint, obs_mean), bp_index + self.bp_index_offset)
        if self.extend_above and self.breakpoints and obs_mean > self.breakpoints[-1]['high_obs']:
            breakpoint = self.breakpoints[-1]
            return (breakpoint['function'](breakpoint, obs_mean), len(self.breakpoints) - 1 + self.bp_index_offset)
        raise IndexError('AQI can not be calculated from this table')

class ArithmeticMean(AqiCalculator):
    '''Simply calculates the arithmetic mean of a set of observations.'''
    def __init__(self, **kwargs):
        kwargs['mean_calculator'] = arithmetic_mean
        super(ArithmeticMean, self).__init__(**kwargs)

    def _calculate_index_from_mean(self, obs_mean):
        return (obs_mean, None)

class LinearScale(AqiCalculator):
    '''Linearly interpolates an observation range to an AQI range.
        low_obs
            low point on the scale in observed units (default 0)
        high_obs (REQUIRED)
            high point on the scale in observed units
        low_aqi
            low point on the AQI scale in indexed values (default 0)
        high_aqi
            high point on the AQI scale in indexed values (default 100)
        breakpoints (REQUIRED)
            Like BreakpointTable. Maps AQIs to categories. List of starting values
            for each category.
    '''
    def __init__(self, **kwargs):
        super(LinearScale, self).__init__(**kwargs)
        self.interpolation_config = {
            'low_obs': kwargs.get('low_obs', 0),
            'high_obs': kwargs['high_obs'],
            'low_aqi': kwargs.get('low_aqi', 0),
            'high_aqi': kwargs.get('high_aqi', 100)
        }
        self.breakpoints = kwargs['breakpoints']

    def _calculate_index_from_mean(self, obs_mean):
        score = linear_interpolate(self.interpolation_config, obs_mean)
        for (i, low) in enumerate(self.breakpoints):
            if i < (len(self.breakpoints) - 1):
                if (low <= score) and (score < self.breakpoints[i + 1]):
                    index = i
                    break
            else:
                index = i
        return (score, index)
