"""Canonical South African province names used in official SAPS tables."""

CANONICAL_PROVINCES = (
    "Eastern Cape",
    "Free State",
    "Gauteng",
    "KwaZulu-Natal",
    "Limpopo",
    "Mpumalanga",
    "North West",
    "Northern Cape",
    "Western Cape",
)

# casefold / stripped aliases map onto the official spelling
_ALIASES = {name.casefold(): name for name in CANONICAL_PROVINCES}


class UnknownProvinceError(ValueError):
    """A value that should be one of the nine official provinces is not recognised."""


def canonical_province(name) -> str:
    key = str(name).strip().casefold()
    if key not in _ALIASES:
        raise UnknownProvinceError(f"unknown province: {name!r}")
    return _ALIASES[key]


def normalise_geo(df):
    """Normalise province names where the official schema uses one of the nine.

    Station rows carry the province in ``Province``. Province-level rows carry it
    in ``area`` (the ``Province`` column there is ``RSA``). Other levels are left
    unchanged. Unknown values raise ``UnknownProvinceError``.
    """
    out = df.copy()
    st = out["level"] == "Station"
    if st.any():
        out.loc[st, "Province"] = out.loc[st, "Province"].map(canonical_province)
    prov = out["level"] == "Province"
    if prov.any():
        out.loc[prov, "area"] = out.loc[prov, "area"].map(canonical_province)
    return out
