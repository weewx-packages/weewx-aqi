# weewx-aqi

Independent continuation of https://github.com/jonathankoren/weewx-aqi.
Preserve the upstream history, copyright and license notices.
Keep existing data formats unless a documented issue requires a change.
Use local fixtures for device, network and filesystem tests.

Run `python -m pytest -q tests` with WeeWX, NumPy and pytest installed.
Keep the EPA revision classes and stored standard IDs distinct. The ozone
reference fixture records the separately executed primary R implementation.
