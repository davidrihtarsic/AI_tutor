POGOSTE TEŽAVE PRI MOBILNEM ROBOTU ZA SLEDENJE ČRTI
================================================================================

Ta dokument je namenjen podpori učencem pri reševanju najpogostejših **neprogramskih težav**, ki se pojavljajo pri sestavljanju, povezovanju in testiranju mobilnega robota za vožnjo po črti. Zajema mehanske, električne in senzorske napake ter predlaga možne vzroke in rešitve.

## Kdo naj uporablja ta dokument?

- **Učenci**: za samostojno odpravljanje napak in refleksijo.
- **GPT tutor**: kot referenco pri odgovarjanju na vprašanja učencev.
- **Učitelji**: kot pripomoček za vodenje učnih aktivnosti.

## Navodilo za GPT Asistenta:

Če učenec opiše težavo, ki se ujema z opisom v tem dokumentu, najprej preveri tukaj naštete možne vzroke. Nato ga vodi z vprašanji skozi preverjanje, brez dajanja končnih rešitev.

Vsaka napaka v tem dokumentu je označena z naslovom na ravni `###`. GPT naj išče relevantno napako tako, da primerja učenčev opis s temi naslovi. Če najde ujemanje, naj izvede sledeče:
1. Preveri možne vzroke pod to napako.
2. Postavi učencu diagnostična vprašanja, povezana z vsakim od vzrokov.
3. Nato predlaga možne ukrepe za odpravo napake – vedno naj vodi z vprašanji ali predlogi, ne z neposrednimi navodili.

---

Spodaj so zbrane najpogostejše napake, razvrščene po področjih. Vsaka vključuje:
- simptom,
- možne vzroke,
- predloge za preverjanje in odpravo napake.

---

### Napaka: Robot se sploh ne premika

**Možni vzroki:**
- Baterije so prazne ali nepravilno vstavljene
- Napajalno stikalo na bateriji je v položaju OFF
- ENABLE stikalo na RobDuinu je izklopljeno

**Predlogi za odpravo:**
- Preveri LED indikatorje na napajalnem modulu
- Napolni baterije in preveri njihovo polariteto
- Preveri položaj stikala ENABLE na modulu RobDuino

---

### Napaka: Robot se vrti v krogu namesto da bi se peljal naravnost

**Možni vzroki:**
- Eno kolo ni dobro nameščeno na os
- Eno od koles se ne vrti zaradi slabe mehanske povezave reduktorja
- Eno od motorjev ni priključen pravilno ali ne deluje

**Predlogi za odpravo:**
- Zavrti kolesi ročno in preveri trenje
- Zamenjaj motorja med seboj in opazuj, ali se težava ponovi
- Preveri priključke motorjev na izhodih D4–D7
- Preveri stanje priključkov D4-D7, če so v logični 1 (če led poleg izhoda sveti)

---

### Napaka: Senzor ne zaznava razlike med črno in belo

**Možni vzroki:**
- Napačen upor v delilniku napetosti (premajhen ali prevelik)
- Napačna priključitev referenčnega upora (med A0 in GND)
- Senzor ni usmerjen proti podlagi
- Prevelika oddaljenost senzorja od podlage
- Zunanja svetloba moti zaznavanje
- Senzor je brez zaslonke (pokrovčka)

**Predlogi za odpravo:**
- Uporabi upor 100kΩ ali 330kΩ za delilnik napetosti
- Približaj senzor podlagi (do 5–10 mm)
- Preizkusi senzor nad črno in nad belo podlago in preveri vrednosti v serijskem monitorju
- Zaščiti senzor z zaslonko (s pokrovčkom) pred ambientno svetlobo

---

### Napaka: Eden od motorjev ne deluje

**Možni vzroki:**
- Ena izmed žic motorja ni dobro priključena
- Izbrani izhod (npr. D6 ali D4) ni v logični `1`
- Motor je mehansko blokiran ali pokvarjen

**Predlogi za odpravo:**
- Preveri in ponovno pritisni konektorje na motorju in RobDuinu
- Po potrebi razširi konektor žice, ki gre v motor
- Zamenjaj motorja med seboj – opazuj, ali se težava ponovi
- Preveri, ali izhod na D4, D5 ali D6, D7 deluje z LED diodo ali multimetrom

---

### Napaka: Motorja se vrtita v napačnih smereh

**Možni vzroki:**
- Motorja sta zamenjana med levim in desnim izhodom
- Žici na posameznem motorju sta zamenjani (+ in −)
- Program krmili napačne pine (čeprav ni programski fokus, lahko pride do zamenjave tudi fizično)

**Predlogi za odpravo:**
- Zamenjaj motorja med izhodoma D4–D7 in opazuj spremembo
- Zamenjaj zaporedje žic na motorju in preveri smer vrtenja
- Preveri, ali se robot vrti v smeri, kot jo pričakuješ pri `moveForward()`

