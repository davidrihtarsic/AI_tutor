# ELORA26 import – 2026-05-30
Ta paket je pretvorba starega `Elora26.json` v podatkovno strukturo AI Classroom Tutorja.
## Ključne predpostavke
- vsi pogovori so umeščeni v datum **2026-05-30**; izvorni JSON nima časovnih žigov;
- vsak izvorni `thread_id` je pretvorjen v eno JSONL sejo;
- tutor je nastavljen na `robotics`, dejavnost na splošni pogovor (`null`), `classroom_revision = 1`;
- časi so sintetični in namenjeni pravilnemu kronološkemu prikazu; niso zgodovinski dokaz dejanskega časa pogovora;
- klasifikacije so rekonstruirane iz vprašanj po sedanji taksonomiji Robotike; ker niso bile v izvoru, so ocene;
- `possible_misconception` je pri uvozu namenoma nastavljen na `null`, razen če bi bila napačna predstava nedvoumna; avtomatsko je nismo sklepali iz dvoumnih starih vprašanj;
- uporabniška imena so narejena iz imen in po potrebi dobijo pripono `_2`, `_3` …; gesla `elora01`, `elora02` … so izmišljena samo za združljivost z današnjim sistemom;
- vsi uporabniki so uvrščeni v oddelek `ELORA26`, registracija oddelka pa je zaprta.
## Obseg
- uporabnikov: **38**
- sej: **38**
- parov vprašanje–odgovor: **179**
## Preslikava uporabnikov

| Izvorni ID | Izvorno ime | Novo uporabniško ime | Novo geslo | Sporočil |
|---|---|---|---|---:|
| `345345` | David | `david` | `elora01` | 32 |
| `01190096` | Nik Trampuš | `nik_trampus` | `elora02` | 2 |
| `70097931` | Maria | `maria` | `elora03` | 5 |
| `70097687` | Hynek | `hynek` | `elora04` | 3 |
| `1305005505371` | Eliška | `eliska` | `elora05` | 3 |
| `70097702` | Ömer | `omer` | `elora06` | 7 |
| `70097672` | Chiara | `chiara` | `elora07` | 9 |
| `70097683` | Nela | `nela` | `elora08` | 3 |
| `70097700` | Matt | `matt` | `elora09` | 2 |
| `1388992` | Matt | `matt_2` | `elora10` | 1 |
| `01190108` | Maja | `maja` | `elora11` | 10 |
| `5810507` | Matt | `matt_3` | `elora12` | 2 |
| `6276437` | omer | `omer_2` | `elora13` | 1 |
| `4629650` | n | `n` | `elora14` | 3 |
| `4024939` | omer | `omer_3` | `elora15` | 2 |
| `2340391` | Matt | `matt_4` | `elora16` | 1 |
| `2118614` | hynek | `hynek_2` | `elora17` | 1 |
| `290645` | omer | `omer_4` | `elora18` | 2 |
| `6318515` | MARIA | `maria_2` | `elora19` | 4 |
| `9617238` | teresa | `teresa` | `elora20` | 2 |
| `3904605` | anonym | `anonym` | `elora21` | 8 |
| `858757` | Matt | `matt_5` | `elora22` | 2 |
| `1647126` | anonay | `anonay` | `elora23` | 11 |
| `841401` | Matt | `matt_6` | `elora24` | 0 |
| `506004` | Matt | `matt_7` | `elora25` | 4 |
| `hynek` | You | `you` | `elora26` | 0 |
| `528469` | hynek | `hynek_3` | `elora27` | 4 |
| `7181146` | haha | `haha` | `elora28` | 1 |
| `236880` | anonym | `anonym_2` | `elora29` | 2 |
| `1377950` | ls | `ls` | `elora30` | 4 |
| `401687` | lja l | `lja_l` | `elora31` | 1 |
| `223356` | anonym | `anonym_3` | `elora32` | 16 |
| `1112167` | omer | `omer_5` | `elora33` | 6 |
| `3890627` | alno | `alno` | `elora34` | 7 |
| `8781829` | omer | `omer_6` | `elora35` | 8 |
| `2935306` | Maja | `maja_2` | `elora36` | 8 |
| `349022` | Matt | `matt_8` | `elora37` | 1 |
| `91375` | Jakob | `jakob` | `elora38` | 1 |

## Rekonstruirana porazdelitev tem

- `general_robotics`: 39
- `line_following`: 32
- `digital_io`: 20
- `light_sensor`: 16
- `distance_sensor`: 15
- `analog_io`: 15
- `robot_construction`: 14
- `motor_control`: 10
- `pwm`: 9
- `robot_behavior`: 6
- `loops`: 2
- `measurement`: 1

## Datoteke

```text
data/
├── users.json
├── classes.json
├── students/
│   └── <nickname>.json
└── sessions/
    └── 2026-05-30/
        └── <session_id>.jsonl
```
