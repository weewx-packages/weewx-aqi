# weewx-aqi
Copyright 2018 - 2021 -- Jonathan Koren <jonathan@jonathankoren.com>

This independent continuation calculates AQI values from archived pollutant
readings. The published catalog archive is `1.5.0.post20261022`, based on
source release 1.5.0. It targets WeeWX 5.5.2–5.6 and Python 3.10–3.14 and adds
a managed backfill module to the source release.

## Supported indices
`weewx-aqi` *is not* an air quality monitor. Instead, it calculates an air
quality index from various pollutants. Air quality indices are single numbers
that are meant to succinctly describe how safe the air is. `weewx-aqi` can
calculate the following indices:

* Australia's Air Quality Index
* Australia's Interim Web Reporting Particulate Index (February 2020)
* Canada's Air Quality Health Index
* European Union's European Air Quality Index
* European Union's Common Air Quality Hourly Index
* India's National Air Quality Index
* Mexico's Índice Metropolitano de la Calidad del Aire
* United Kingdom's Daily Air Quality Index
* United States's Air Quality Index
* United States's NowCast Air Quality Index


## Prerequisites
A source for air quality data, such as
[`weewx-purpleair`](https://github.com/bakerkj/weewx-purpleair) .


## Installation

For a pip installation, activate the existing virtual environment that runs
your WeeWX service before running these commands. Both `python` and `weectl`
must come from that environment. For a distribution package installation, use
its `weectl`, with `sudo` if required. Add `--config /path/to/weewx.conf` to the
extension command when your station configuration is not found automatically.

For Debian or Raspberry Pi OS package installations, use
`sudo apt install python3-numpy` when selecting `NowCast2019`. Its version must
satisfy `numpy>=2.2,<3`. If your distribution does not supply that version, use
a WeeWX virtual environment. The pip command below is for that environment.

Use a NumPy wheel matching your Python and platform. A NumPy source build
requires C/C++ compilers, Python headers, BLAS/LAPACK development libraries and
`pkg-config`;
see the [NumPy build prerequisites](https://numpy.org/doc/stable/building/).

Use an existing pollutant data source and its archive binding. Install NumPy
in the WeeWX environment if you select the `NowCast2019` ozone model:

```sh
python -m pip install 'numpy>=2.2,<3'
```

Install the published archive with WeeWX 5's extension installer:

```sh
weectl extension install https://github.com/weewx-packages/catalog/releases/download/aqi/v1.5.0.post20261022/aqi-1.5.0.post20261022.tar.gz
```

Restart your WeeWX service after configuration, for example
`sudo systemctl restart weewx` on systemd. The installer does not restart it
for you.

The installer registers `user.aqi.service.AqiService` in `process_services`,
installs the `user.aqi` package, and adds `aqi_binding` with its own `aqi.sdb`
database. Configure the sensor mapping and standard before restarting.
To remove the extension, use `weectl extension uninstall aqi` and restart.
Back up configuration and AQI databases before an upgrade or backfill.

By default, the install script configures `weewx-aqi` for use with
`weewx-purpleair` and calculates a United States's NowCast AQI. If you are not
using `weewx-purpleair`, or wish to use a different air quality index, you will
need to modify your `weewx.conf`.

When configuring a different air quality sensor, you need to set the
`data_binding` of sensor readings, and provide a schema of columns to pollutants.
along with a column storing the reading's timestamp in epoch seconds UTC, and
a column with the semantics of WeeWx's `usUnits`. Optional columns for
temperature, and atmospheric pressure are helpful, but not required.

The configurable schema columns are:
* `dateTime`: *required* Timestamp of the reading in epoch seconds UTC.
* `usUnits`: *required* Unit system the readings are stored in.
* `temp`: *optional* Temperature at the sensor.
* `pressure`: *optional* Atmospheric at the sensor.
* `pm2_5`:  *optional* Particulate matter smaller than 2.5 micrometers
* `pm10_0`:  *optional* Particulate matter smaller than 10 micrometers
* `co`:  *optional* Carbon monoxide
* `no2`:  *optional* Nitrogen dioxide
* `so2`:  *optional* Sulfur dioxide
* `o3`:  *optional* Ozone
* `nh3`:  *optional* Ammonia
* `pb`:  *optional* Lead

All air quality indices, with the exception of Canada's, can be calculated
for a single pollutant. Additionally, all air quality indices can also
calculate composite index. However, this index will only be calculated if
readings are available for all of the requisite components.

After installation, you will need to modify your `weewx.conf`. Mainly, you will
need to connect `weewx-aqi` to the data binding for the air sensor. Assuming
you're using `weewx-purpleair`, you will need to add the following to your
`weewx.conf`.

The default `weewx.conf` block is:
```
[AqiService]
    [[air_sensor]]
        pm2_5 = pm2_5_atm
        temp = purple_temperature
        data_binding = purpleair_binding
        dateTime = dateTime
        pressure = purple_pressure
        pm10_0 = pm10_0_atm
        usUnits = usUnits
    [[standard]]
        data_binding = aqi_binding
        standard = user.aqi.us.NowCast
```

## Display the data
To make use of the plugin you will need to modify the templates in
`/etc/weewx/skins/*.tmpl` to include references to the new data found in
the aqi.sdb file.

### Examples:
#### The Current Value
`$latest($data_binding='aqi_binding').aqi_pm2_5`

#### Maximum Value Today
`$day($data_binding='aqi_binding').aqi_pm2_5.max`

#### Time Today When The Maximum Value Occurred
`$day($data_binding='aqi_binding').aqi_pm2_5.maxtime`

#### Colors and Categories
AQIs have categorical labels associated with the AQI values. The index of the
current category is available via `$latest($data_binding='aqi_binding').aqi_pm2_5_category`.
The AQI color and category can be found using wrapping the index with the`$aqi`
Cheetah template. Add to your `skin.conf`:
```
[CheetahGenerator]
    search_list_extensions = user.aqi.service.AqiSearchList
```
And then in your template (e.g. `index.html.tmpl`), you can add something
similar to this example `<DIV>`, that illustrates display the AQI value,
category, and color:
```
<div style="text-align: center; background-color: #$aqi($current($data_binding='aqi_binding').aqi_pm2_5_category).color;" >
    $current($data_binding='aqi_binding').aqi_pm2_5 <br/>
    $aqi($current($data_binding='aqi_binding').aqi_pm2_5_category).category
</div>
```

## Units
AQIs are dimensionless.

You can also graph these values by adding the appropriate
configuration to your `skin.conf` file:
```
    [[[dayaqi]]]
        data_binding = aqi_binding
        [[[[aqi_pm2_5]]]]
```

The values stored in the database are:
```
aqi_composite,
aqi_composite_category,
aqi_pm2_5,
aqi_pm2_5_category,
aqi_pm10_0,
aqi_pm10_0_category,
aqi_co,
aqi_co_category,
aqi_no2,
aqi_no2_category,
aqi_so2,
aqi_so2_category,
aqi_o3,
aqi_o3_category,
aqi_nh3,
aqi_nh3_category,
aqi_pb,
aqi_pb_category,
```

## Additional utilities

The catalog archive installs the backfill command as `user.aqi.backfill`.
With WeeWX's Python environment active and `/path/to/station/bin` replaced by
the parent of your installed `user` directory:

```sh
PYTHONPATH=/path/to/station/bin python -m user.aqi.backfill --help
PYTHONPATH=/path/to/station/bin python -m user.aqi.backfill /path/to/weewx.conf --start_time 1767225600 --end_time 1769904000
```

The range arguments are Unix timestamps in seconds. This example covers
January 2026 in UTC. Check the destination binding and back up the database first. Stop WeeWX
while backfilling. The source launcher `bin/aqi_backfill` is retained in the
archive but is not installed as a top-level command.


## Development testing

Install the NumPy dependency from [Installation](#installation) before testing.
With Git installed and that WeeWX virtual environment active, download the
source into an empty working directory:

```sh
git clone --depth 1 https://github.com/weewx-packages/weewx-aqi.git
cd weewx-aqi
python -m unittest
```

## Independent continuation

This repository continues [jonathankoren/weewx-aqi](https://github.com/jonathankoren/weewx-aqi)
from d5bf9c9f28e8da15e3a65c55bc623e56a42e3602. It retains the complete upstream
history, copyright and GPLv3 license and is maintained separately.

Version 1.5.0 is tested with WeeWX 5.5.2 on Python 3.10 and 3.14. Install with
the catalog archive linked above. The default PurpleAir mapping
and existing standard names remain available. The Python 2 compatibility
package `six` is no longer required.

### Choose the EPA revision

The `standard` option in `[AqiService][[standard]]` selects the calculation:

| Class in `user.aqi.us` | PM2.5 table | Ozone method | Stored standard ID |
| --- | --- | --- | --- |
| `AirQualityIndex` | Original table | Original trailing means | 5 |
| `NowCast` | Original table | Original legacy method | 6 |
| `AirQualityIndex2024` | May 2024 | Original trailing means | 11 |
| `NowCast2024` | May 2024 | Original legacy method | 12 |
| `NowCast2019` | May 2024 | EPA 2019 model, including reference updates through 2021 | 13 |

The new modes use all six PM2.5 intervals from
[40 CFR Part 58 Appendix G, Table 2, 2024 edition](https://www.govinfo.gov/content/pkg/CFR-2024-title40-vol6/pdf/CFR-2024-title40-vol6-part58-appG.pdf).
The changes include the upper intervals. They use the 301–500 slope to
extrapolate numeric hazardous values above 500, as specified in the table's
footnote. New EPA modes round half values upward. The old class names retain
their tables and original integer-rounding behavior.

Existing stored rows are not recalculated on upgrade. For historical comparisons,
keep each revision in a separate AQI binding/database. Conversion corrections,
zero-temperature handling and accurate floating-point summation can change newly
calculated values that previously encountered those bugs, including legacy modes.
The old gas conversion multiplied ppb into ppm and divided ppm into ppb; the
correct relationship is one ppm equals 1000 ppb. Singular, plural and modern
WeeWX `ppm`/`ppb` unit names are accepted. Column names and database types remain
unchanged.

The new particulate NowCast accepts two valid hours among the latest three;
it does not require a twelve-hour warmup. An hour needs 75 percent of its
expected archive samples. Missing or rejected samples stay missing, and the
weighted mean uses the actual hour positions. The calculation follows the
[AirNow technical assistance document, section IV](https://document.airnow.gov/technical-assistance-document-for-the-reporting-of-daily-air-quailty.pdf).

For `NowCast2019`, install NumPy using the environment-specific instructions
under [Installation](#installation).

The ozone model uses a 336-hour history and the EPA decision tree, including
surrogate, zero and missing-hour cases. Two extra hours allow it to reconstruct
an earlier-hour result after a restart. A rank-deficient model produces a
missing result. The full-component model uses centered least squares when its
predictor matrix has full rank. Tests compare its concentrations with the
actually executed [EPA R reference](https://github.com/USEPA/O3-Nowcast), including
the EPA example dataset, to an absolute tolerance of 1e-8 ppb. Fixture provenance
and source hashes are in `tests/fixtures/epa_ozone_reference.json`.

### Read PM from the main archive or Davis AirLink

The AirLink extension supplies `pm2_5` and `pm10_0`. Once those fields are stored
in your weather archive, this configuration also works for custom PM sensors:

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

`usUnits = usUnits` names the database column holding each row's WeeWX unit-system
code. It does not select US units for the sensor. Set `[standard] obs_frequency_in_sec` to
the actual spacing of the stored sensor records if it differs from the default
`[StdArchive] archive_interval`. Temperature and pressure are
unnecessary when the pollutant already has the required concentration units.
For gas/mass conversion, configure both sensor temperature and station pressure,
for example `temp = extraTemp1` and `pressure = pressure`. Zero Celsius is valid.
Missing conversion context leaves that pollutant missing. Humidity is not used.

Keep SQL NULL values for unavailable readings. The calculators ignore them
subject to their completeness rules. Out-of-table values in legacy modes produce
NULL AQI/category fields and a log message instead of terminating WeeWX.
No synthetic maximum or replacement sensor value is stored.

The Canadian `user.aqi.ca.AirQualityHealthIndex` needs O3, NO2 and PM2.5 together;
its three-hour calculators and composite constructor now work. It does not
provide individual-pollutant AQHI values. Sensor wiring, AirLink device access
and live data are outside these local fixture tests.

### Backfill an extended archive

The backfill tool reads the archive's named timestamp/interval columns and uses
the configured table and bindings. It does not start the station driver. This
avoids assigning extended or reordered columns using a fixed standard schema.
It writes using the selected standard, so choose the destination binding before
running it. The start timestamp is included; the end timestamp is excluded.

### Tests

Run `python -m pytest -q tests` with WeeWX, NumPy and pytest installed. Tests
cover the actual service and SQLite databases, custom temperature columns,
missing readings, 2024 boundaries, gas conversions, NowCast completeness,
Canadian composite construction, and the separately executed EPA ozone reference.


The previously unimportable Australian module also has its indentation,
interim constructor name and missing category bands repaired. The six bands
follow the [Australian government report, table 8](https://soe.dcceew.gov.au/sites/default/files/2022-07/soe2021-air-quality.pdf).
The interim particulate thresholds retain the original 80.1 and 62.1 values,
which are documented in the [NSW air-quality glossary](https://www.environment.nsw.gov.au/topics/air/understanding-air-quality-data/glossary-of-air-quality-terms).
These are the historical methods represented by the existing class names.
