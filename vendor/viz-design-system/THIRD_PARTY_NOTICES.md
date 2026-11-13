# Code, fonts and native dependencies

The authored source, page kit, adapters, styles and synthetic fixtures use the [MIT licence](LICENSE). The bundled fonts keep their own licences. Publication requires separate approval of the exact export snapshot.

## Bundled fonts (release 2.0.2)

Each file is an unmodified WOFF2 file (latin subset) from a pinned Fontsource package. Each family's copyright notice and the complete SIL Open Font License 1.1 text are kept beside the fonts. `assets/fonts/manifest.json` records each file's package, version, byte length, SHA256, source URL and modification status.

| Family | Role | File | Bytes | SHA256 | Package | Licence file |
|---|---|---|---|---|---|---|
| Newsreader 500 | Headings | `newsreader-latin-500-normal.woff2` | 23624 | `5613e2fc8377392c02e8ac9d55014689fb5320a5f2a7be55e8088a314728ac2c` | `@fontsource/newsreader` 5.2.10 | `newsreader.LICENSE.txt` |
| Newsreader 600 | Headings | `newsreader-latin-600-normal.woff2` | 23876 | `05c91a26d19a61eafe7ce8e0b77eff3fd279ce994dc89f432f4cd06784935e84` | `@fontsource/newsreader` 5.2.10 | `newsreader.LICENSE.txt` |
| Public Sans 400 | Body | `public-sans-latin-400-normal.woff2` | 14632 | `36274b5787b4f03b27e65ae971d6c808a96838ccd60c9dabaee154889b6bba82` | `@fontsource/public-sans` 5.2.7 | `public-sans.LICENSE.txt` |
| Public Sans 600 | Body | `public-sans-latin-600-normal.woff2` | 14592 | `c7842f97346df1b3b470e9d71acde90f132dd858508ec5ae6606401e5d0938f7` | `@fontsource/public-sans` 5.2.7 | `public-sans.LICENSE.txt` |
| IBM Plex Mono 400 | Figures | `ibm-plex-mono-latin-400-normal.woff2` | 14708 | `08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7` | `@fontsource/ibm-plex-mono` 5.2.7 | `ibm-plex-mono.LICENSE.txt` |
| IBM Plex Mono 500 | Figures | `ibm-plex-mono-latin-500-normal.woff2` | 14888 | `01d285447409c8a588692162439a038b8cbd7871309ee20267b0d2d91c6e8e22` | `@fontsource/ibm-plex-mono` 5.2.7 | `ibm-plex-mono.LICENSE.txt` |

Total font bytes: 106,320 (release 2.0.0 and 2.0.1: 190,820, with a 132,000-byte Newsreader variable file from `@fontsource-variable/newsreader` 5.2.10). Licence file hashes: Newsreader `26028ec4e13b650065fa525a09532176f8a668b76ff849ea01c564a7480f91e7`, Public Sans `705a497c781f6463ff819abb513bb495f3fb05256f1d20321e3275813c0bafa5`, IBM Plex Mono `23b0a9d0c6d3f140a0b77e483c5cfa6bba574325ef5cb189ed9f2fec4884533f`. All are SIL Open Font License 1.1; the IBM Plex notice names IBM Corp., the others their project authors. Font licences also apply when the same bytes are embedded in generated stylesheets (`pilots/marimo-theme.css`) or the standalone chart (`assets/specimen-bar.svg`, which embeds Public Sans 400 and 600 and IBM Plex Mono 400).

Release 1.0.0 bundled Source Sans 3 and Source Serif 4. They are no longer in the release 2 source; release 1's export and its notices remain unchanged in `public-export/`.

## Separately installed native tools

The bootstrap installs native packages from the frozen locks. The reusable source archive contains no installed virtual environment, node_modules directory or compiled native web build. Installed direct-package metadata declares these licences:

| Package | Version | Declared licence |
|---|---|---|
| Observable Framework | 1.13.4 | ISC |
| Evidence | 40.1.8 | MIT |
| Evidence core components | 5.4.2 | MIT |
| Evidence Tailwind plugin | 3.1.4 | MIT |
| Streamlit | 1.64.0 | Apache-2.0 |
| marimo | 0.25.0 | Apache-2.0 |
| Plotly | 7.1.0 | MIT |

These declarations describe the named packages, not their transitive dependencies or generated browser bundles. A consumer distributing a native build must keep the applicable upstream licences and notices and inventory that build's actual resources.

## Test tools

The glyph-width test and the JavaScript formatter and theme-control tests run on Node's built-in modules (Node 24). Browser evidence used Playwright with Chromium and axe-core 4.10.3 (MPL-2.0), installed outside this archive.

## Candidate packaging

From this project's directory, run `make release-candidate RELEASE_OUTPUT=releases/2.3.0`, then `make release-check RELEASE_OUTPUT=releases/2.3.0`. The builder refuses an existing output directory and never touches `public-export/`. The manifest records every file's byte length and SHA256 and always marks the archive as an unaccepted candidate with no publication approval.

For a trusted snapshot comparison, use `python3 -B src/build_release.py --output /absolute/path/to/candidate --check --expected-manifest-sha256 HASH`, replacing `HASH` with the manifest digest recorded when that snapshot was reviewed. Integrity checks do not replace the copy, accessibility, performance, review, claims or reproduction gates.
