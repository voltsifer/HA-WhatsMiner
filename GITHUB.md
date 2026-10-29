# GitHub and HACS

Project repository: **https://github.com/voltsifer/HA-WhatsMiner**.

## Installation and updates

1. Open **HACS → menu ⋮ → Custom repositories**.
2. Add `https://github.com/voltsifer/HA-WhatsMiner`, category **Integration**.
3. Download HA-WhatsMiner and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → HA-WhatsMiner**.

HACS installs the single integration at `custom_components/whatsminer_local`, including the card JavaScript. Resource registration is documented in [HEATMAP.md](HEATMAP.md).

Without a GitHub Release, installation uses the default branch. Check the **Actions** tab for current CI results. Inclusion in the default HACS catalog is a separate process and is not required to install this custom repository.

## Development

Integration source is in `custom_components/whatsminer_local`, tests in `tests`, and CI in `.github/workflows/tests.yml`. The manifest declares the integration version. Web chip retrieval supports the LuCI `btminerapi` syslog format, plain text and normalized JSON; actual firmware compatibility must be verified against a saved device response.

`tools/configure_repository.py` updates local repository URLs and code owners when moving the project. It does not create repositories or publish files.

All current project text is English. CI runs `tools/check_english.py` to reject Cyrillic text and removed language files. Binary demo artwork is regenerated with English labels.

The repository is public. Enter passwords and cookies in Home Assistant; real credentials are not included in source control.

References:

- https://www.hacs.xyz/docs/publish/integration/
- https://www.hacs.xyz/docs/faq/custom_repositories/
