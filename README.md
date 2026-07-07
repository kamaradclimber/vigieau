# Vigieau for home-assistant

Component to expose water restrictions in France through Vigieau api. See https://vigieau.gouv.fr/ for web access.

This integration share location via a 3rd party (government) website (as the website does).

Data is based on the [vigieau](https://www.data.gouv.fr/fr/datasets/donnee-secheresse-vigieau/) dataset. It's really great to have access to such data.

![downloads](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.vigieau.total)


## Installation

It must be used as a custom repository via HACS.

## Configuration

Once the custom integration has been added, add "vigieau" integration through the UI.

You can choose the location either by using HA coordinates (default), giving a specific town zip code or select a point in a map.

![image info](/img/vigieau_location.png)

HA coordinates are the one defined during initial setup and accessible using (`System>General>Edit location`)

Once a first location is added a new one can be added (using city zip code or a pin on a map)

### Using Zip Code
![image info](/img/location.png)

Localisation is based on INSEE Code, not ZIP/Postal code. If several INSEE code correspond to provided Zip code, manual selection will be required..

![image info](/img/multiloc.png)

### Selecting a point on map
![image info](/img/vigieau_map.png)

## Known issues and workaround

### Error communicating with API: Impossible to find approximate address of the current HA instance. API returned no result.

This integration uses a geocoding API to get the city code from INSEE (used as a input by Vigieau API). It is based on governement data which is still incomplete in some France areas.

A workaround can be used by setting the `VIGIEAU_FORCED_INSEE_CITY_CODE` environment variable with the city code as value.
⚠ Value of city code is not necessarily city "postal code". You can find it easily of wikipedia under the name [code commune](https://fr.wikipedia.org/wiki/Code_officiel_g%C3%A9ographique#Code_commune).

## Sensors

Two sensors are created for each water usage category:

| Type | Description | Diagnostic category | Enabled by default |
|---|---|---|---|
| `sensor` | Textual restriction level (native value: "Aucune restriction", "Interdiction", "Interdiction sur plage horaire", etc.) | No | No |
| `binary_sensor` | `on` = allowed, `off` = restricted | Yes | Yes for fountains, vegetable gardens, lawns, car wash, swimming pools |

### Attributes

All sensors expose these additional attributes for automations:

| Attribute | Description |
|---|---|
| `currently_restricted` | `true` if a restriction is currently active |
| `restriction` | Textual restriction level (same as string sensor native value) |
| `next_restriction_start` | (time-based restrictions only) Next restriction start time (ISO format) |
| `next_restriction_end` | (time-based restrictions only) Next restriction end time (ISO format) |
| `Categorie: <name>` | Exact API description for that usage |
| `<name> (details)` | Additional usage details from the API |
| `heureDebut` / `heureFin` | (if unambiguous) Restriction time window |
