import pytest

def test_gas_mass_roundtrip_uses_molecular_mass():
    from bin.user.aqi import units
    for pollutant, mass in [('o3', 47.997), ('co', 28.010), ('so2', 64.058)]:
        expected = 0.123 * 1000.0 * (98.0 / 8.31446) * mass / 293.15
        concentration = units.convert_pollutant_units(pollutant, 0.123, 'ppm',
            'microgram_per_meter_cubed', 293.15, 98.0)
        assert concentration == pytest.approx(expected, abs=0.001)
        actual = units.convert_pollutant_units(pollutant, concentration, 'microgram_per_meter_cubed',
            'parts_per_million', 293.15, 98.0)
        assert actual == pytest.approx(0.123, abs=0.000001)


