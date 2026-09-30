---
id: robot_movement
title: Funkcije robota
tutor: robotics
order: 10
description: Osnovno krmiljenje pogonskih motorjev in izdelava datoteke PremikiRobota.h.
enabled: true
---

# Vožnja robotka s programskimi funkcijami

## Namen aktivnosti

Pri aktivnosti boste najprej neposredno krmilili oba pogonska motorja robotka z digitalnimi izhodi krmilnika. Tako boste povezali električno vezavo motorjev z ukazi `digitalWrite()` in ugotovili, katera kombinacija izhodnih stanj povzroči premik naprej.

Takoj po prvem uspešnem premiku boste delujočo programsko kodo združili v funkcijo `robotNaprej()` in jo shranili v header datoteko:

`PremikiRobota.h`

V nadaljevanju boste datoteko postopoma dopolnjevali s funkcijami:

`robotNaprej();`
`robotStop();`
`robotLevo();`
`robotDesno();`
`robotNazaj();`

## Povezava pogonskih motorjev

Robot ima dva pogonska motorja.

### Levi pogonski motor

Levi motor je povezan na digitalna izhoda:

* D7
* D6

Za vrtenje v smeri naprej mora biti:

`D7 = 0`
`D6 = 1`

oziroma v programu:

`digitalWrite(7, LOW);`
`digitalWrite(6, HIGH);`

### Desni pogonski motor

Desni motor je povezan na digitalna izhoda:

* D5
* D4

Za vrtenje v smeri naprej mora biti:

`D5 = 1`
`D4 = 0`

oziroma:

`digitalWrite(5, HIGH);`
`digitalWrite(4, LOW);`

Tako za vožnjo robotka naprej potrebujemo kombinacijo:

| Motor       | Priključek 1 | Priključek 2 | Stanje za vožnjo naprej |
| ----------- | ------------ | ------------ | ----------------------- |
| Levi motor  | D7           | D6           | `D7=0`, `D6=1`          |
| Desni motor | D5           | D4           | `D5=1`, `D4=0`          |

## 1. Prvi premik robotka

Najprej pripravite digitalne izhode za krmiljenje motorjev:

`D7, D6, D5, D4`

kot izhode.

Nato napišite program, s katerim se bo robotek:

1. premikal naprej,
2. vozil približno dve sekundi,
3. nato ustavil.

Za vožnjo naprej uporabite stanja:

`D7=0`
`D6=1`
`D5=1`
`D4=0`

Na podlagi teh stanj napišite ustrezne ukaze `digitalWrite()`.

Ko robot uspešno zapelje naprej, primerjajte programsko kodo z vedenjem robotka.

### Razmislek

Ali je iz zaporedja štirih `digitalWrite()` ukazov na prvi pogled jasno, da pomenijo:

> robot vozi naprej?

Kako bi lahko ta del kode naredili bolj berljiv?

## 2. Ustvarimo funkcijo `robotNaprej()`

Kodo za vožnjo naprej združite v funkcijo:

`robotNaprej();`

V funkciji boste uporabili pravkar ugotovljena stanja pogonskih motorjev.

Primer strukture:

`void robotNaprej()`

znotraj katere nastavite:

* levi motor: `D7=0`, `D6=1`;
* desni motor: `D5=1`, `D4=0`.

Glavni program lahko nato namesto štirih ukazov vsebuje samo:

`robotNaprej();`

S tem koda veliko jasneje pove, kaj robot dejansko počne.

## 3. Ustvarimo header datoteko `PremikiRobota.h`

Ker bomo funkcij za premikanje robotka potrebovali več, jih bomo zapisali v ločeno header datoteko:

`PremikiRobota.h`

V datoteko najprej shranite:

`robotNaprej();`

V glavnem programu jo vključite z:

`#include "PremikiRobota.h"`

Glavni program lahko nato izgleda zelo preprosto:

`robotNaprej();`
`delay(2000);`

Podrobnosti, kateri priključki morajo biti HIGH ali LOW, so sedaj skrite v funkciji.

To je pomemben korak k bolj berljivi in pregledni programski kodi.

## 4. Dodajmo funkcijo `robotStop()`

Z eksperimentiranjem ugotovite, katera stanja motorjev povzročijo ustavitev.

Nato v `PremikiRobota.h` dodajte funkcijo:

`robotStop();`

Program preizkusite tako:

`robotNaprej();`
`delay(2000);`
`robotStop();`

## 5. Dodajmo druge smeri

Sedaj ugotovite, kako morata biti krmiljena levi in desni motor, da robot:

* zapelje nazaj;
* zavije levo;
* zavije desno.

Vsako novo vedenje najprej preizkusite z neposrednimi `digitalWrite()` ukazi.

Ko deluje pravilno, ga pretvorite v funkcijo in dodajte v:

`PremikiRobota.h`

Na koncu naj datoteka vsebuje vsaj:

`robotNaprej();`
`robotNazaj();`
`robotLevo();`
`robotDesno();`
`robotStop();`

