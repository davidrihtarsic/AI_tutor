---
id: distance_sensor
title: Senzor razdalje
tutor: robotics
order: 20
description: Uporaba senzorja Sharp GP2Y0A21 in izogibanje oviram.
enabled: true
---

# Aktivnost: Robot zaznava ovire

## Namen aktivnosti

Pri tej aktivnosti boste robotku dodali **analogni infrardeči senzor razdalje Sharp GP2Y0A21**. Najprej boste raziskali, kakšen signal daje senzor pri različnih oddaljenostih ovire. Nato boste izmerjeno vrednost uporabili kot vhodni podatek za odločanje o gibanju robota.

Robot bo najprej izvajal zelo preprosto pravilo:

**če ni ovire → vozi naprej**
**če zazna oviro → se ustavi**

Program boste nato nadgradili tako, da se bo robot oviri tudi **samostojno izmaknil**.

Pri programiranju gibanja uporabljajte funkcije iz datoteke `PremikiRobota.h`.

---

## Učni cilji

Študent:

* pravilno priključi analogni senzor razdalje;
* z ukazom `analogRead()` prebere analogni vhod;
* uporablja serijsko komunikacijo za spremljanje meritev;
* z eksperimentiranjem razišče odziv senzorja na spremembo razdalje;
* uporabi pogojni stavek za odločanje na podlagi meritve;
* poveže zaznavanje okolice z gibanjem robota;
* izdela preprosto reaktivno vedenje robota;
* z opazovanjem in preizkušanjem izboljšuje vedenje robota.

# 1. Priključitev senzorja

Uporabljamo analogni infrardeči senzor razdalje **Sharp GP2Y0A21**.

Senzor priključite na 3-pinski priključek RobDuino modula:

| Senzor                   | RobDuino |
| ------------------------ | -------- |
| GND                      | GND      |
| napajanje                | +5 V     |
| signal – **rumena žica** | **A0**   |

Pred priključitvijo preverite orientacijo priključka. Posebej bodite pozorni, da je **rumena signalna žica senzorja priključena na A0**.

# 2. Najprej opazujmo senzor

Preden senzor uporabite za krmiljenje robota, raziščite njegovo delovanje.

V programu preberite analogni vhod:

`analogRead(A0)`

Dobljeno vrednost pošljite na serijsko vodilo in jo opazujte v **Serial Monitorju**.

Program naj torej:

1. prebere A0;
2. izpiše izmerjeno vrednost;
3. nekoliko počaka;
4. meritev ponovi.

### Eksperiment

Pred senzor postavite večji predmet in ga počasi premikajte proti senzorju ter stran od njega.

Opazujte vrednosti.

Poskusite odgovoriti:

* Kakšna je vrednost, ko je ovira daleč?
* Kaj se z vrednostjo dogaja, ko oviro približujete?
* Ali se vrednost spreminja enakomerno z razdaljo?
* Ali je meritev popolnoma stabilna, če predmet miruje?
* Ali senzor enako dobro zazna različne predmete in površine?

Ne poskušajte še pretvarjati meritve v centimetre. Za prvo vedenje robota potrebujemo predvsem informacijo:

**Ali je pred robotom ovira ali ne?**

# 3. Izberimo prag

Za začetek bomo uporabili vrednost:

`400`

Opazujte meritve in poiščite približno razdaljo, pri kateri senzor doseže to vrednost.

Razmislite, kaj v našem primeru pomeni:

`vrednost < 400`

in kaj:

`vrednost >= 400`

Prag `400` ni univerzalna fizikalna meja. Je vrednost, ki jo bomo uporabili za prvo preprosto odločanje robota.

# 4. Robot se odzove na oviro

Vključite datoteko:

`PremikiRobota.h`

in uporabite že izdelani funkciji:

`robotNaprej();`

`robotStop();`

Program naj neprestano bere senzor in izvaja naslednje pravilo:

**Če je vrednost senzorja manjša od 400, naj robot pelje naprej. Sicer naj se ustavi.**

Osnovna struktura odločitve je:

`if (razdalja < 400)`

→ `robotNaprej();`

sicer:

→ `robotStop();`

Program naložite na robot in ga preizkusite.

Pred robot postavite oviro.

Ali se robot pravočasno ustavi?

### Eksperimentirajte

Poskusite prag `400` spremeniti.

Kaj se zgodi pri:

`300`

`500`

`600`

Pri kateri vrednosti se robot za vaš senzor in hitrost gibanja ustavlja na primerni razdalji od ovire?

S tem ste izdelali prvo povezavo:

**SENZOR → ODLOČITEV → GIBANJE**

Robot se sedaj ne premika več samo po vnaprej določenem zaporedju. Njegovo vedenje je odvisno od tega, **kaj zazna v okolici**.

# 5. Ustavljanje še ni dovolj

Trenutni robot ima težavo.

Ko pride do ovire:

`robotStop();`

Toda ovira je še vedno pred njim.

Kaj bi moral narediti, da bi lahko nadaljeval vožnjo?

Preden napišete program, sestavite smiselno zaporedje vedenja.

Ena možnost je:

**STOP → NAZAJ → LEVO → NAPREJ**

S funkcijami iz `PremikiRobota.h` lahko to zapišemo kot zaporedje:

`robotStop();`

`robotNazaj();`

`robotLevo();`

`robotNaprej();`

Določiti morate še, **koliko časa** naj posamezen gib traja.

# 6. Robot se izmakne oviri

Nadgradite program.

Dokler pred robotom ni ovire, naj velja:

**NAPREJ**

Ko robot zazna oviro, naj izvede manever:

1. ustavi se;
2. nekoliko zapelje nazaj;
3. zavije levo;
4. nadaljuje vožnjo naprej.

Časov posameznih gibov ne prevzemite kot vnaprej podane vrednosti.

**Poiščite jih z eksperimentiranjem.**

Če robot po vožnji nazaj še vedno zadene oviro, kaj morate spremeniti?

Če se pri zavijanju obrne premalo, kaj morate spremeniti?

Če se obrne preveč?

Spreminjajte program, opazujte robota in izboljšujte njegovo vedenje.

# 7. Preizkus v prostoru

Postavite robotka na tla in v prostoru pripravite več ovir.

Opazujte njegovo vedenje.

Ali lahko robot dalj časa samostojno vozi po prostoru, ne da bi trčil?

Bodite pozorni na primere, ko algoritem ne deluje dobro:

* približevanje oviri pod kotom;
* vogal;
* ozka pot;
* različne površine ovir;
* robot se po umiku ponovno obrne proti isti oviri.

Takšni primeri niso samo napake. So pomembna informacija o **omejitvah našega trenutnega algoritma**.

## Dodatni izziv: izboljšajte vedenje

Poskusite sami izboljšati strategijo izogibanja.

Robot se trenutno vedno umakne na enak način:

**nazaj → levo**

Kaj bi lahko naredili drugače?

Razmislite na primer:

* Ali bi se lahko včasih obrnil desno?
* Ali potrebuje vedno vožnjo nazaj?
* Bi lahko na odločitev vplivala izmerjena vrednost senzorja?
* Kaj se zgodi, če robot zazna oviro takoj po končanem izmikanju?
* Kako bi preprečili, da se robot ujame v ponavljanje enakega manevra?

Najprej oblikujte idejo, nato jo preizkusite na robotu.

# Vprašanja za razmislek

1. Kaj nam vrne `analogRead(A0)`?
2. Zakaj smo meritve najprej opazovali v Serial Monitorju, preden smo jih uporabili za krmiljenje?
3. Kaj predstavlja prag `400`?
4. Kaj se zgodi, če prag povečamo?
5. V čem se ta program razlikuje od predhodnega programa za ples robotkov?
6. Zakaj je zaporedje `STOP → NAZAJ → LEVO → NAPREJ` samo ena od možnih strategij?
7. Katere omejitve ste opazili pri zaznavanju ovir?
8. Kaj bi robot potreboval, da bi se lahko o smeri izmikanja odločal bolje?

# Vloga AI tutorja

AI tutor naj pri tej aktivnosti posebej spodbuja povezovanje **meritve, odločitve in vedenja robota**.

Če študent vpraša:

> Kakšno vrednost moram nastaviti namesto 400?

naj tutor ne poda nove vrednosti, ampak ga usmeri v meritev:

> V Serial Monitorju opazuj vrednost pri razdalji, na kateri želiš, da robot začne reagirati. Kakšno vrednost izmeriš?

Če študent vpraša:

> Koliko časa naj robot zavija levo?

naj ga tutor spodbuja k eksperimentu:

> Izberi začetni čas, preizkusi zavoj na robotu in opazuj rezultat. Če se obrne premalo, kako bi spremenil čas?

Če študent zahteva celoten program za izogibanje oviri, naj tutor najprej pomaga oblikovati **vedenje oziroma zaporedje korakov**, ne pa takoj napisati celotne rešitve.

Osrednji učni proces aktivnosti naj bo:

**meritev → opazovanje → odločitev → gibanje → preizkus → izboljšava**

S tem robot postopoma prehaja od naprave, ki samo izvaja vnaprej zapisane premike, k preprostemu **reaktivnemu sistemu, ki svoje vedenje prilagaja zaznanemu okolju**.
