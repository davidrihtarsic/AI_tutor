# AI Classroom Tutor

Modularen prototip spletnega AI tutorja za uporabo pri pouku. Ena aplikacija lahko gosti več vsebinsko različnih tutorjev (npr. robotika, elektronika), **učitelj pa za ves razred določa aktivnega tutorja in dejavnost**. Učenci se prijavijo samo z vzdevkom in geslom ter uporabljajo klepetalnik.

Projekt ohranja učne vsebine pregledne in prenosljive:

- navodila in strokovna vsebina so v **Markdownu**,
- strukturirane nastavitve in stanje so v **JSON-u**,
- dogodki so v **JSONL-u**,
- OpenAI Vector Store je trajni iskalni indeks, ki se sinhronizira iz lokalnih Markdown datotek.

## Glavne funkcije

- več neodvisnih tutorjev v eni aplikaciji;
- persistentni OpenAI Vector Store za vsakega tutorja;
- samodejno ustvarjanje in SHA-256 sinhronizacija Vector Stora;
- prijava učencev z `nickname + password`;
- učitelj centralno izbira **tutorja + dejavnost** za ves razred;
- sprememba učiteljeve konfiguracije velja za vse učence pri naslednjem vprašanju;
- ob spremembi konfiguracije se ustvari nova `revision`, zato novi tutor ne podeduje starega pogovornega konteksta;
- strukturirana klasifikacija vprašanj in učiteljski dashboard;
- lahek model učenca v JSON-u;
- Markdown prikaz odgovorov tutorja;
- JSONL dnevniki za kasnejšo analizo.

## 1. Namestitev

Zahtevan je Python 3.11 ali novejši.

Na Arch Linuxu, če želite pakete namestiti sistemsko:

```bash
sudo pacman -S python-pip
pip install --break-system-packages -r requirements.txt
```

Na sistemu, kjer `pip` dovoljuje navadno sistemsko namestitev, zadostuje:

```bash
pip install -r requirements.txt
```

## 2. OpenAI API

```bash
cp .env.example .env
```

V `.env` vnesite API ključ:

```text
OPENAI_API_KEY=sk-...
```

Datoteke `.env` ne objavljajte na GitHubu.

## 3. Uporabniki

Ob prvem dostopu aplikacija samodejno kopira:

```text
data/users.example.json
```

v lokalno:

```text
data/users.json
```

Primer:

```json
[
  {
    "nickname": "robot01",
    "password": "motor1",
    "enabled": true
  }
]
```

**Pomembno:** gesla so v tej prototipni različici namenoma shranjena v čisti obliki, da lahko učitelj učencu hitro pove pozabljeno geslo. Ta rešitev je primerna samo za zaupanja vredno lokalno šolsko omrežje in ni primerna za javno internetno namestitev. `data/users.json` je v `.gitignore`.

## 4. Sinhronizacija strokovnih baz

En tutor:

```bash
python scripts/sync_vector_stores.py robotics
```

Vsi tutorji:

```bash
python scripts/sync_vector_stores.py --all
```

Ob prvi sinhronizaciji program sam ustvari Vector Store in shrani njegov ID v `data/config/vector_stores.json`. Kasneje se po SHA-256 prenesejo samo spremembe.

## 5. Zagon

```bash
uvicorn app:app --reload
```

Lokalno:

```text
http://127.0.0.1:8000
```

Za dostop drugih računalnikov v istem LAN-u:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## 6. Potek za učenca

Učenec vedno odpre isti naslov aplikacije in vidi samo prijavo:

```text
vzdevek + geslo -> Prijava -> Klepetalnik
```

Učenec **ne izbira tutorja in dejavnosti**. S tem ne more sam spreminjati načina podpore.

## 7. Potek za učitelja

Odprite:

```text
http://127.0.0.1:8000/teacher/login
```

PIN je nastavljen v `.env`:

```text
TEACHER_PIN=1234
```

Na dashboardu učitelj izbere:

```text
Tutor:      Robotika
Dejavnost:  Robot sesalnik
```

in klikne **Uporabi za ves razred**.

Aktivna nastavitev je shranjena v:

```text
data/config/classroom.json
```

Vsako novo učenčevo vprašanje prebere to datoteko. Zato lahko učitelj med uro spremeni tutorja ali dejavnost in sprememba začne veljati za vse trenutno prijavljene učence pri njihovem naslednjem vprašanju.

Vsaka dejanska sprememba poveča `revision`. Zgodovina na učenčevem zaslonu ostane vidna, model pa dobi samo dialog trenutne revizije. To prepreči, da bi npr. Elektronika nadaljevala kontekst prejšnjega tutorja Robotika.

Spremembe se beležijo v:

```text
data/config/classroom_events.jsonl
```

## 8. Tutor in dejavnost

Tutor določa predvsem:

- področje,
- splošna didaktična navodila (`tutor.md`),
- taksonomijo tem (`topics.json`),
- strokovno bazo (`knowledge/*.md` / Vector Store).

Dejavnost (`activities/*.md`) doda kontekst konkretne naloge, cilje, opremo, omejitve in posebna didaktična navodila. Če dejavnost ni izbrana, tutor deluje kot **Splošni pogovor**.

## 9. Struktura vsebin

```text
tutors/robotics/
├── metadata.json
├── topics.json
├── tutor.md
├── knowledge/
│   ├── motors.md
│   ├── sensors.md
│   └── programming.md
└── activities/
    └── robot_vacuum.md
```

Velja načelo:

- `.md` = vsebina, ki jo predvsem piše in bere človek,
- `.json` = strukturirane nastavitve/stanje,
- `.jsonl` = zaporedje dogodkov.

## 10. Klasifikacija in model učenca

Vsako vprašanje se klasificira (`intent`, `topic`, `problem_type`, `possible_misconception`, `response_strategy`, `understanding_signal` ...). Podatki služijo prilagajanju pomoči in situacijskemu vpogledu učitelja.

`data/students/<nickname>.json` vsebuje preprost `support_estimate` po temah. To **ni formalna ocena znanja**, ampak negotova interna informacija za prilagajanje odgovorov.

## 11. GitHub in podatki

Repozitorij ne sme vsebovati:

- `.env`,
- `data/users.json`,
- učenčevih JSONL pogovorov,
- modelov učencev,
- `vector_stores.json`,
- trenutne `classroom.json` konfiguracije.

Te poti so vključene v `.gitignore`.

Za podrobnejši arhitekturni opis glejte [STRUCTURE.md](STRUCTURE.md).
