# Struktura projekta

## Temeljna načela

1. **Markdown je vir vsebinske resnice.**
2. **JSON je namenjen strukturiranim podatkom in stanju.**
3. **JSONL je dnevnik dogodkov.**
4. **Vector Store je indeks, ne primarni vir vsebine.**
5. **Tutorje in dejavnost izbira učitelj, ne učenec.**
6. **Aktivna učiteljeva konfiguracija se prebere pri vsakem vprašanju.**

## Drevo projekta

```text
ai-classroom-tutor/
├── app.py
├── config.py
├── models.py
├── README.md
├── STRUCTURE.md
│
├── services/
│   ├── analytics_service.py
│   ├── classroom_service.py      # aktivni tutor/dejavnost + revision
│   ├── openai_service.py
│   ├── storage_service.py
│   ├── tutor_service.py
│   ├── user_service.py           # nickname/password iz users.json
│   └── vector_store_service.py
│
├── tutors/
│   ├── robotics/
│   │   ├── metadata.json
│   │   ├── topics.json
│   │   ├── tutor.md
│   │   ├── knowledge/
│   │   └── activities/
│   └── electronics/
│       └── ...
│
├── templates/
├── static/
│
└── data/
    ├── users.example.json        # primer, lahko je v Git-u
    ├── users.json                # lokalni računi; ni v Git-u
    ├── config/
    │   ├── vector_stores.json    # OpenAI IDs/hash-i; ni v Git-u
    │   ├── classroom.json        # trenutna učiteljeva nastavitev
    │   └── classroom_events.jsonl
    ├── students/
    │   └── <nickname>.json
    └── sessions/
        └── YYYY-MM-DD/
            └── <session_id>.jsonl
```

## Potek prijave

```text
učenec odpre /
      │
      ▼
nickname + password
      │
      ▼
data/users.json
      │
      ▼
ustvari se student chat session
      │
      ▼
/chat/<session_id>
```

Pogovorna seja vsebuje identiteto učenca, vendar **ne predstavlja avtoritativnega vira tutorja/dejavnosti**.

## Učiteljeva konfiguracija

```text
UČITELJ
   │
   ├── tutor_id
   └── activity_id
          │
          ▼
data/config/classroom.json
```

Primer:

```json
{
  "tutor_id": "robotics",
  "activity_id": "robot_vacuum",
  "revision": 4,
  "updated_at": "..."
}
```

Vsaka sprememba tutorja ali dejavnosti poveča `revision`.

## Potek enega vprašanja

```text
učenec pošlje vprašanje
          │
          ▼
preberi classroom.json        <-- vedno trenutno stanje
          │
          ├── tutor.md
          ├── activity.md
          ├── topics.json
          └── pravi Vector Store
          │
          ▼
moderacija + klasifikacija
          │
          ▼
zapis student_message v JSONL
          │
          ▼
model učenca
          │
          ▼
AI tutor + file_search
          │
          ▼
odgovor + tutor_message JSONL
```

## Meja konteksta ob spremembi

Vsak `student_message` in `tutor_message` vsebuje `classroom_revision`.

Ko učitelj spremeni konfiguracijo:

```text
revision 3: Robotika + Robot sesalnik
revision 4: Elektronika + Splošni pogovor
```

učenec na strani še vedno vidi stare odgovore, vendar se modelu pri revision 4 pošlje samo pogovor revision 4. Tako nova pedagoška konfiguracija ne podeduje starega konteksta.

## Gesla

`data/users.json` vsebuje gesla v čisti obliki **namenoma**. Razlog je hitro reševanje pozabljenih gesel v lokalnem šolskem prototipu. Učitelj jih vidi na dashboardu. Datoteka je izključena iz Git-a.

To je varnostni kompromis in ni primeren za javno internetno namestitev.

## Vector Store

V Vector Store sodijo samo:

```text
tutors/<tutor_id>/knowledge/**/*.md
```

`tutor.md` in `activities/*.md` se podajo neposredno modelu kot trenutna navodila/kontekst.
