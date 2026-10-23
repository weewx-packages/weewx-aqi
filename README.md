# weewx-aqi

`weewx-aqi` calculates air quality indices from pollutant readings that are
already stored in a WeeWX database. It is not an air quality monitor and does
not read sensors itself.

This repository is an independent continuation of
[jonathankoren/weewx-aqi](https://github.com/jonathankoren/weewx-aqi), started
from d5bf9c9f28e8da15e3a65c55bc623e56a42e3602 with the complete upstream
history.

## Requirements

* A source of air quality data that stores its readings in a WeeWX database,
  such as [`weewx-purpleair`](https://github.com/bakerkj/weewx-purpleair) or a
  sensor extension that writes `pm2_5` and `pm10_0` into the weather archive.
* NumPy, only for the `user.aqi.us.NowCast2019` standard. Install it in the
  Python environment that runs WeeWX:

  ```sh
  python -m pip install 'numpy>=2.2,<3'
  ```

  For a Debian or Raspberry Pi OS package installation, use
  `sudo apt install python3-numpy` if the distribution's NumPy satisfies the
  same range. Otherwise run WeeWX in a virtual environment. Use a NumPy wheel
  for your Python and platform. A source build needs C/C++ compilers, Python
  headers, BLAS/LAPACK development libraries and `pkg-config`; see the
  [NumPy build prerequisites](https://numpy.org/doc/stable/building/).

## Installation

Install `aqi` from the [WeeWX packages catalog](https://github.com/weewx-packages/catalog/blob/main/packages/aqi.md).
The catalog page lists the current release, its WeeWX and Python
requirements, and the install, update and removal commands.

The installer registers `user.aqi.service.AqiService` in `process_services`,
adds the `[AqiService]` section and adds `aqi_binding` with its own `aqi.sdb`
database. Its default sensor mapping expects `weewx-purpleair`. Adjust
`[AqiService]` as described under [Configuration](#configuration), then
restart WeeWX. Back up the configuration and the AQI database before an
upgrade.

## Configuration

The installer writes this block, which reads `weewx-purpleair` and calculates
the United States NowCast AQI:

```ini
[AqiService]
    [[standard]]
        data_binding = aqi_binding
        standard = user.aqi.us.NowCast
    [[air_sensor]]
        data_binding = purpleair_binding
        usUnits = usUnits
        dateTime = dateTime
        temp = purple_temperature
        pressure = purple_pressure
        pm2_5 = pm2_5_atm
        pm10_0 = pm10_0_atm
```

### `[[standard]]`

| Option | Default | Meaning |
| --- | --- | --- |
| `data_binding` | required | Binding the calculated values are written to. |
| `standard` | required | Class of the index to calculate, see [Choose the index](#choose-the-index). |
| `obs_frequency_in_sec` | `[StdArchive] archive_interval` | Spacing of the stored sensor records in seconds. Must be positive. |

### `[[air_sensor]]`

`data_binding` is required. Every other option names a column in that
binding's table.

| Option | Default | Column |
| --- | --- | --- |
| `data_binding` | required | Binding that holds the sensor readings. |
| `dateTime` | `dateTime` | Timestamp of the reading in epoch seconds UTC. |
| `usUnits` | `usUnits` | WeeWX unit system code of each row. It does not select US units. |
| `temp` | none | Temperature at the sensor. |
| `pressure` | none | Atmospheric pressure at the sensor. |
| `pm2_5` | none | Particulate matter up to 2.5 micrometers. |
| `pm10_0` | none | Particulate matter up to 10 micrometers. |
| `co` | none | Carbon monoxide. |
| `no2` | none | Nitrogen dioxide. |
| `so2` | none | Sulfur dioxide. |
| `o3` | none | Ozone. |
| `nh3` | none | Ammonia. |
| `pb` | none | Lead. |

Temperature and pressure are only needed to convert between gas fractions
(ppm, ppb) and mass concentrations. If both `temp` and `pressure` are set,
they are read from the sensor binding. Otherwise `outTemp` and `pressure` are
read from the main weather archive. Zero Celsius is valid. Without a usable
temperature and pressure, a pollutant that needs conversion stays missing.
Humidity is not used. `ppm`, `ppb` and the singular and plural WeeWX unit
names are accepted.

Every index except Canada's can be calculated for a single pollutant. The
composite index is only calculated when columns are configured for all
pollutants of the selected standard.

### Choose the index

Set `standard` to one of these classes:

| Index | `standard` |
| --- | --- |
| Australia's Air Quality Index | `user.aqi.au.AirQualityIndex` |
| Australia's Interim Web Reporting Particulate Index (February 2020) | `user.aqi.au.InterimWebReportingParticulateIndex` |
| Canada's Air Quality Health Index | `user.aqi.ca.AirQualityHealthIndex` |
| European Union's European Air Quality Index | `user.aqi.eu.EuropeanAirQualityIndex` |
| European Union's Common Air Quality Hourly Index | `user.aqi.eu.CommonAirQualityHourlyIndex` |
| India's National Air Quality Index | `user.aqi.india.NationalAirQualityIndex` |
| Mexico's Índice Metropolitano de la Calidad del Aire | `user.aqi.mx.IndiceMetropolitanoCalidadAire` |
| United Kingdom's Daily Air Quality Index | `user.aqi.uk.DailyAirQualityIndex` |
| United States's Air Quality Index | `user.aqi.us.AirQualityIndex` and EPA revisions below |
| United States's NowCast Air Quality Index | `user.aqi.us.NowCast` and EPA revisions below |

The United States classes select the EPA revision. Each one stores its own
standard ID in the `aqi_standard` column:

| Class in `user.aqi.us` | PM2.5 table | Ozone method | Stored standard ID |
| --- | --- | --- | --- |
| `AirQualityIndex` | Original table | Original trailing means | 5 |
| `NowCast` | Original table | Original legacy method | 6 |
| `AirQualityIndex2024` | May 2024 | Original trailing means | 11 |
| `NowCast2024` | May 2024 | Original legacy method | 12 |
| `NowCast2019` | May 2024 | EPA 2019 model, including reference updates through 2021 | 13 |

The May 2024 classes use all six PM2.5 intervals from
[40 CFR Part 58 Appendix G, Table 2, 2024 edition](https://www.govinfo.gov/content/pkg/CFR-2024-title40-vol6/pdf/CFR-2024-title40-vol6-part58-appG.pdf),
including the upper intervals. Above 500 they extrapolate with the 301–500
slope, as the table's footnote specifies. They round half values upward. The
original classes keep their tables and integer rounding.

The particulate NowCast of `NowCast2024` and `NowCast2019` needs two valid
hours among the latest three. It does not need a twelve-hour warmup. An hour
is valid with 75 percent of its expected archive samples. Missing or rejected
samples stay missing, and the weighted mean uses the actual hour positions.
The calculation follows the
[AirNow technical assistance document, section IV](https://document.airnow.gov/technical-assistance-document-for-the-reporting-of-daily-air-quailty.pdf).

The `NowCast2019` ozone model needs NumPy, see [Requirements](#requirements).
It uses a 336-hour history and the EPA decision tree, including surrogate,
zero and missing-hour cases. Two extra hours let it reconstruct an
earlier-hour result after a restart. A rank-deficient model gives a missing
result. With a full-rank predictor matrix, the full-component model uses
centered least squares. The tests compare its concentrations with the executed
[EPA R reference](https://github.com/USEPA/O3-Nowcast), including the EPA
example dataset, to an absolute tolerance of 1e-8 ppb. Fixture provenance and
source hashes are in `tests/fixtures/epa_ozone_reference.json`.

The Australian index uses the six bands of the
[Australian government report, table 8](https://soe.dcceew.gov.au/sites/default/files/2022-07/soe2021-air-quality.pdf).
The interim particulate index keeps the original thresholds of 80.1 and 62.1,
documented in the
[NSW air-quality glossary](https://www.environment.nsw.gov.au/topics/air/understanding-air-quality-data/glossary-of-air-quality-terms).

For historical comparisons, keep each revision in a separate AQI binding and
database.

### Read PM from the main archive or Davis AirLink

The AirLink extension supplies `pm2_5` and `pm10_0`. Once those fields are
stored in your weather archive, this configuration reads them. It also works
for other PM sensors that write these fields:

```ini
[AqiService]
    [[standard]]
        data_binding = aqi_binding
        standard = user.aqi.us.NowCast2024
    [[air_sensor]]
        data_binding = wx_binding
        dateTime = dateTime
        usUnits = usUnits
        pm2_5 = pm2_5
        pm10_0 = pm10_0
```

PM2.5 and PM10 need no temperature or pressure when they are stored as mass
concentrations. For gases stored in the other unit, configure both, for
example `temp = extraTemp1` and `pressure = pressure`.

Keep SQL NULL for unavailable readings. The calculators skip them, subject to
their completeness rules. A value outside the table of an original class gives
NULL AQI and category fields and a log message. No synthetic maximum or
replacement value is stored.

### Show the values in a report

The calculated values are stored in the `aqi_binding` database. AQIs are
dimensionless. The columns are:

```
aqi_composite, aqi_composite_category,
aqi_pm2_5, aqi_pm2_5_category,
aqi_pm10_0, aqi_pm10_0_category,
aqi_co, aqi_co_category,
aqi_no2, aqi_no2_category,
aqi_so2, aqi_so2_category,
aqi_o3, aqi_o3_category,
aqi_nh3, aqi_nh3_category,
aqi_pb, aqi_pb_category
```

Use them in your skin's templates with the `aqi_binding` data binding:

| Value | Tag |
| --- | --- |
| Current value | `$latest($data_binding='aqi_binding').aqi_pm2_5` |
| Maximum today | `$day($data_binding='aqi_binding').aqi_pm2_5.max` |
| Time of today's maximum | `$day($data_binding='aqi_binding').aqi_pm2_5.maxtime` |
| Index of the current category | `$latest($data_binding='aqi_binding').aqi_pm2_5_category` |

The `$aqi` tag turns a category index into its color and label. Add the search
list extension to your `skin.conf`:

```ini
[CheetahGenerator]
    search_list_extensions = user.aqi.service.AqiSearchList
```

Then use it in a template such as `index.html.tmpl`:

```html
<div style="text-align: center; background-color: #$aqi($current($data_binding='aqi_binding').aqi_pm2_5_category).color;" >
    $current($data_binding='aqi_binding').aqi_pm2_5 <br/>
    $aqi($current($data_binding='aqi_binding').aqi_pm2_5_category).category
</div>
```

To plot a value, add an image to the `[ImageGenerator]` section of your
`skin.conf`:

```ini
    [[[dayaqi]]]
        data_binding = aqi_binding
        [[[[aqi_pm2_5]]]]
```

### Backfill existing readings

The installer adds the backfill tool as the module `user.aqi.backfill`.
Activate the Python environment that runs WeeWX and replace
`/path/to/station/bin` with the directory that contains your installed `user`
directory:

```sh
PYTHONPATH=/path/to/station/bin python -m user.aqi.backfill --help
PYTHONPATH=/path/to/station/bin python -m user.aqi.backfill /path/to/weewx.conf --start_time 1767225600 --end_time 1769904000
```

The range arguments are Unix timestamps in seconds. The start is included and
the end is excluded. This example covers January 2026 in UTC. Without a range,
the whole archive is processed.

The tool reads the timestamp and interval columns of the `wx_binding` archive
by name and uses the configured tables and bindings. It does not start the
station driver. It writes with the configured standard to the configured
`[[standard]] data_binding`, so check that binding first. Stop WeeWX and back
up the AQI database before backfilling.

## Limitations

* Stored rows are not recalculated when the calculation changes. The
  continuation corrected gas conversions, zero-temperature handling and
  floating-point summation. Newly calculated values can differ from older rows
  that hit those bugs, including in the original classes. The old gas
  conversion multiplied ppb into ppm and divided ppm into ppb; one ppm equals
  1000 ppb. Column names and database types are unchanged.
* `user.aqi.ca.AirQualityHealthIndex` needs O3, NO2 and PM2.5 together. It does
  not provide individual-pollutant values.
* The tests use local fixtures and SQLite databases. Sensor wiring, AirLink
  device access and live data are not tested.

## Development

Run the tests from the repository root with WeeWX, NumPy and pytest installed
in the active environment:

```sh
python -m pytest -q tests
```

They cover the service with SQLite databases, custom temperature columns,
missing readings, the 2024 boundaries, gas conversions, NowCast completeness,
the Canadian composite, the backfill tool and the separately executed EPA
ozone reference.

## License

Copyright 2018 - 2021 -- Jonathan Koren <jonathan@jonathankoren.com>

Licensed under the GNU General Public License version 3. See
[LICENSE](LICENSE).
