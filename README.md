
# AI Tutor

AI Tutor je spletna aplikacija, ki omogoča študentom/dijakom/učencem klepet z GPT asistentom. Vključuje tudi administrativni vmesnik za upravljanje pogovorov študentov.

## Način uporabe

### Študentski vmesnik

1. Odprite glavno stran za klepet z navigacijo na osnovni URL (`https://UČITELJEV_IP_NASLOV:5000`).
2. Vnesite svoje ime in po želji svojo študentsko številko.
3. Kliknite gumb "Prijava" za začetek seje.
4. Vnesite svoja vprašanja v vnosno polje za sporočila in kliknite "Pošlji" za klepet z GPT asistentom.

### Administrativni vmesnik

1. Odprite administrativno stran z navigacijo na `https://127.0.0.1/admin`.
2. Izberite asistenta iz spustnega menija.
3. Izberite skupino pogovorov za ogled pogovorov.
4. Preklopite status vnosnega polja za sporočila z drsnikom.

## Namestitev

### Predpogoji

- Python 3.x
- Flask
- OpenAI knjižnica
- Dodatne Python knjižnice (navedene spodaj)

### Koraki

1. Klonirajte repozitorij:
    ```sh
    git clone https://github.com/yourusername/AI_tutor.git
    cd AI_tutor
    ```

2. Ustvarite virtualno okolje in ga aktivirajte:
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Namestite potrebne knjižnice:
    ```sh
    pip install -r requirements.txt
    ```

4. Ustvarite datoteko `config.json` v korenski mapi z vašim OpenAI API ključem in ID-ji asistentov:
    ```json
    {
        "api_key": "your_openai_api_key",
        "ai_elora_1": "assistant_id_1",
        "ai_elora_2": "assistant_id_2"
    }
    ```

5. Ustvarite mapo `conversations` v korenski mapi za shranjevanje datotek pogovorov:
    ```sh
    mkdir conversations
    ```

6. Zaženite aplikacijo:
    ```sh
    python AiTutor.py
    ```

7. Odprite svoj spletni brskalnik in navigirajte na `http://localhost:5000` za študentski vmesnik ali `http://localhost:5000/admin` za administrativni vmesnik.

## Potrebne knjižnice

- Flask
- OpenAI
- Marked (za Markdown razčlenjevanje)
- Highlight.js (za sintaksno označevanje)

Namestite te knjižnice z naslednjim ukazom:
```sh
pip install flask openai
```

Dodatno vključite naslednje v svoje HTML datoteke:
```html
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/default.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/cpp.min.js"></script>
```

## Licenca

Ta projekt je licenciran pod MIT licenco.