# weewx-aqi
# Modified 2026-10-22: implement the EPA ozone NowCast decision tree.
# License: GPL 3
"""Ozone NowCast from the EPA reference published in 2019 and updated in 2021.

The full-component PLS prediction equals centered least squares for a full-rank
predictor matrix. Tests compare it with the actual EPA R implementation. NumPy
is optional and is imported only when this standard is selected.
"""
import math

from . import calculators


def ozone_nowcast(values, previous=None):
    """Calculate an ozone NowCast concentration from 336 hourly ppb values.

    Args:
        values (list[float|None]): Hourly means, oldest first, including missing hours.
        previous (dict|None): Earlier NowCast concentrations keyed by hours ago.

    Returns:
        tuple[float|None, int]: Concentration and EPA method ID, or None if unavailable.

    Raises:
        ValueError: The input length or model rank does not permit a prediction.
    """
    import numpy as np

    if len(values) != 336:
        raise ValueError('Ozone NowCast requires a 336-hour window')
    previous = previous or {}
    data = np.asarray(values, dtype=float)
    valid = np.isfinite(data) & (data >= 0)
    data[~valid] = np.nan
    if not valid.any():
        return None, 8
    missing_run = 0
    longest_run = 0
    for present in valid:
        missing_run = 0 if present else missing_run + 1
        longest_run = max(longest_run, missing_run)
    rolling = np.full(336, np.nan)
    for i in range(4, 333):
        window = data[i-4:i+4]
        if np.isfinite(window).sum() >= 6:
            rolling[i] = np.nanmean(window)
    if valid.sum() < 252 or longest_run > 7 or np.isnan(rolling[95:]).mean() > 0.25:
        for offset, method in [(0, 3), (1, 5), (2, 7)]:
            if valid[-1-offset]:
                return float(data[-1-offset] * 0.85 + 4.5), method
        return None, 8
    if np.nansum(data) == 0:
        return 0.0, 1
    if not valid[-1]:
        if valid[-2]:
            return previous.get(1), 4
        if valid[-3]:
            return previous.get(2), 6
        return None, 8
    # Impute from the original neighbours, using imputeTS's exponential weights.
    imputed = data.copy()
    for missing_index in np.flatnonzero(~valid):
        width = 4
        while True:
            indices = np.arange(max(0, missing_index-width), min(336, missing_index+width+1))
            indices = indices[valid[indices]]
            if len(indices) >= 2:
                break
            width += 1
        weights = 2.0 ** -np.abs(indices-missing_index)
        imputed[missing_index] = np.sum(data[indices] * weights) / np.sum(weights)
    predictors = np.array([imputed[i-95:i+1] for i in range(95, 336)])
    response = rolling[95:]
    training = np.isfinite(response)
    x_mean = predictors[training].mean(axis=0)
    y_mean = response[training].mean()
    coefficients, residuals, rank, singular_values = np.linalg.lstsq(
        predictors[training]-x_mean, response[training]-y_mean, rcond=None)
    if rank < 96:
        raise ValueError('Ozone NowCast predictor matrix is rank deficient')
    prediction = float((predictors[-1]-x_mean) @ coefficients+y_mean)
    if not math.isfinite(prediction):
        return None, 8
    return (0.0, 1) if prediction < 0 else (prediction, 2)


class OzoneNowCast2019(calculators.AqiCalculator):
    """Combine the EPA ozone prediction with the 8-hour and 1-hour AQI tables."""

    def __init__(self, obs_frequency_in_sec):
        # Fail at configuration time if the optional numerical dependency is absent.
        import numpy
        super(OzoneNowCast2019, self).__init__(unit='parts_per_billion',
            duration_in_secs=338*calculators.HOUR, obs_frequency_in_sec=obs_frequency_in_sec)
        self.eight_hour = calculators.BreakpointTable(unit=self.unit,
            duration_in_secs=8*calculators.HOUR, obs_frequency_in_sec=obs_frequency_in_sec)
        for row in [(0,50,0,54),(51,100,55,70),(101,150,71,85),(151,200,86,105),(201,300,106,200)]:
            self.eight_hour.add_breakpoint(*row, function=calculators.epa_linear_interpolate)
        self.one_hour = calculators.BreakpointTable(unit=self.unit,
            duration_in_secs=calculators.HOUR, obs_frequency_in_sec=obs_frequency_in_sec,
            bp_index_offset=2, extend_above=True)
        for row in [(101,150,125,164),(151,200,165,204),(201,300,205,404),(301,500,405,604)]:
            self.one_hour.add_breakpoint(*row, function=calculators.epa_linear_interpolate)

    def calculate(self, pollutant, observation_unit, observations):
        if observation_unit != self.unit:
            raise ValueError('Ozone NowCast expects parts_per_billion')
        if not observations:
            raise ValueError('No ozone observations')
        latest_hour = (max(row['dateTime'] for row in observations)-1)//calculators.HOUR
        hourly = [[] for i in range(338)]
        for row in observations:
            index = 337-(latest_hour-(row['dateTime']-1)//calculators.HOUR)
            value = row.get(pollutant)
            if 0 <= index < 338 and value is not None and math.isfinite(value) and value >= 0:
                hourly[index].append(value)
        needed = calculators.HOUR/self.obs_frequency_in_sec*0.75
        values = [math.fsum(hour)/len(hour) if len(hour) >= needed else None for hour in hourly]
        previous = {}
        if values[-1] is None:
            for offset in [1, 2]:
                if values[-1-offset] is not None:
                    previous[offset] = ozone_nowcast(values[-336-offset:-offset])[0]
        prediction, method = ozone_nowcast(values[-336:], previous)
        if prediction is None:
            raise ValueError('Ozone NowCast unavailable, EPA method %s' % method)
        candidates = []
        try:
            candidates.append(self.eight_hour._calculate_index_from_mean(int(prediction)))
        except IndexError:
            pass
        if values[-1] is not None:
            try:
                candidates.append(self.one_hour._calculate_index_from_mean(int(values[-1])))
            except IndexError:
                pass
        if not candidates:
            raise ValueError('Ozone concentrations do not fall within an applicable AQI table')
        return max(candidates)

    def _calculate_index_from_mean(self, mean):
        raise NotImplementedError()
