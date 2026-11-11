# Świecące Klawisze – pamięć projektu

Ten plik to wspólna pamięć projektu. Claude czyta go na początku każdej rozmowy
i aktualizuje na koniec każdej sesji pracy (sekcje „Stan”, „Decyzje”, „Do zrobienia”, „Dziennik zmian”).
Rozmowy z Łukaszem i cały interfejs aplikacji są **po polsku**.

## Cel

Własna aplikacja na iPada zamiast płatnej subskrypcji VIP w aplikacji Smart Piano.
Najważniejsze: wybór utworów i podświetlanie na keyboardzie klawiszy, które trzeba nacisnąć.

## Sprzęt

- Keyboard **The ONE COLOR Smart Keyboard**: 61 klawiszy, czerwone diody pod każdym klawiszem.
- Łączy się przez **Bluetooth LE MIDI**. Przyjmuje **tylko jedno połączenie**, więc aplikacja Smart Piano musi być całkowicie zamknięta.
- Zakres: najniższy klawisz C2 (MIDI 36), najwyższy C7 (MIDI 96). W aplikacji można to zmienić w Ustawieniach.

## Protokół świateł

Źródło: projekt open-one-piano, licencja MIT, testowany na COLOR:
https://github.com/vhorvath2010/open-one-piano/blob/main/PROTOCOL.md

| Akcja | Bajty |
|---|---|
| Zapal klawisz | `A2 <nuta−21> <kolor>` (Polyphonic Key Pressure, kanał 3) |
| Zgaś klawisz | `A2 <nuta−21> 00` |
| Zgaś wszystkie | `F0 00 20 2B 69 16 02 00 F7` |
| Zapal wszystkie | `F0 00 20 2B 69 16 02 <kolor> F7` |

- Kolor: `01` czerwony, `02` niebieski. COLOR pokazuje oba na czerwono.
- „Start sesji” `F0 00 20 2B 69 00 00 55 F7` to **nasze przypuszczenie**, niepotwierdzone (przycisk eksperymentalny w Ustawieniach).

## Środowisko uruchomieniowe

- Safari na iPadzie **nie obsługuje Web MIDI**. Aplikację otwieramy w **Web MIDI Browser** (App Store, autor Takashi Mizuhiki). Alternatywa: MIDIWeb Browser.
- Web MIDI Browser to stara implementacja:
  - `access.inputs` i `access.outputs` mają tylko `forEach` (bez `.values()` i `.get()`), dlatego jest funkcja `portList()`;
  - nie zawsze zgłasza `statechange`, dlatego co 2 s odpytujemy listę urządzeń;
  - keyboard widać pod nazwą **„Bluetooth Session 1”**, a nie „The ONE”;
  - odbiór działa przez `onmidimessage` i `addEventListener` jednocześnie; duplikaty odfiltrowuje `onMidi()`.
- **Potwierdzone 11.11.2026:** aplikacja działa na iPadzie z Web MIDI Browser.

## Architektura

- Cała aplikacja to **jeden plik `index.html`**: HTML + CSS + JS, bez budowania i bez zewnętrznych bibliotek.
- `lakh.json` – spis piosenek z Lakh MIDI (wykonawca → tytuły, ~375 KB) dla katalogu. Budowany skryptem `tools/lakh_index.py`.
- `swiecace-klawisze.html` przekierowuje do `./` (stary adres z zakładek).
- Hosting: **GitHub Pages** z gałęzi `main`, folder główny. Adres: https://lukaszdomin.github.io/pianino/
  Każdy push na `main` publikuje się w 1–2 minuty.
- Dane użytkownika (wgrane pliki MIDI jako base64, ustawienia) trzymamy w `localStorage` (`sk_songs`, `sk_settings`).
  Utwory z katalogu mają dodatkowe pole `src` (np. `commons:6596429`, `bitmidi:27978`), po którym poznajemy, że już je mamy.
  Każdy utwór ma pole `lvl` (1 łatwe, 2 średnie, 3 trudne, 0 nieznany). Poziomy wyników katalogu są zapamiętane w `sk_levels` (`src` → `{l, d}`).
- Główne części `index.html`:
  - wbudowane utwory: `makeSong()` + tablica `BUILTIN` (notacja `C4:1 D#4:0.5 R:2`, akordy przez `+`);
  - parser plików MIDI: `parseMidi()` – zwraca też `inst` (instrument General MIDI każdej ścieżki, najczęstszy program wśród jej nut);
  - wybór ścieżek: `defaultTracks()` / `melodyTrack()` – utwory wbudowane i fortepian na dwie ręce (≤2 ścieżki fortepianu) → wszystkie ścieżki;
    piosenki z wieloma instrumentami → tylko melodia (`song.melody`, ⭐ przy ścieżce). Punkty: wysokość, brak akordów, granie przez cały utwór,
    instrument (Lead/dęte +, bas/pady/smyczki/efekty −) i nazwa ścieżki (Melody/Vocal mocno, Lead/Solo słabiej, Bass/Pad/Chords −).
    Sprawdzone na plikach z Lakh: ABBA, Haddaway, Madonna, Toto, Darude, Daft Punk, Corona, 2 Unlimited, Eiffel 65. Nazwy instrumentów: tablica `GM`;
  - MIDI i światła: `initMidi()`, `refreshPorts()`, `portList()`, `light()`, `setLit()`, `allOff()`;
  - odtwarzacz: `prepare()` buduje `ns` (nuty) i `steps` (grupy nut), tryby `wait` i `tempo`;
  - katalog utworów z internetu: obiekt `cat`, `catSearch()`, `catCommons()`, `catBitmidi()`, `catLakh()`, `catDownload()`, `renderCatalog()`;
    podpowiedzi `CAT_SUGG` w grupach (Klasyka, Pop i rock, Dance i techno, Święta i dla dzieci);
  - odsłuch w katalogu: `catPreview()` / `pvTick()` / `pvStop()` – plik tylko w pamięci (`catA.buf`, więc „Pobierz” go nie ściąga drugi raz),
    pierwsze 30 s, melodia głośniej, tło max 6 dźwięków naraz, nuty planowane co 100 ms na 0,4 s do przodu; `tone()` przyjmuje czas, głośność i wyjście;
  - poziom trudności: `songLevel()` (punkty za tempo, akordy, rozpiętość, czarne klawisze, >4 ścieżki, długość; 0–2 łatwe, 3–5 średnie, 6+ trudne),
    w katalogu kolejka `catA` / `catPump()` pobiera pliki w tle (po 3 naraz) i liczy poziom; pobrany plik zostaje w pamięci dla „Pobierz”;
  - diagnostyka: `log()`, `diag()`, sekcja Dziennik w Ustawieniach z przyciskiem „Kopiuj dziennik”.

## Jak pracujemy

1. Łukasz zaczyna nową rozmowę od zdania „Pracujemy nad lukaszdomin/pianino” i pisze, co chce zmienić.
2. Claude podłącza repozytorium, czyta ten plik i wprowadza zmiany w `index.html`.
3. Przed każdym pushem: `node --check` na skrypcie i `python3 tests/smoke_test.py` (zasymulowany keyboard w przeglądarce).
4. Push na `main` → GitHub Pages publikuje → Łukasz testuje na iPadzie z prawdziwym keyboardem.
5. Gdy coś nie działa na iPadzie: Ustawienia → „Kopiuj dziennik” → wklejenie w rozmowie.
6. Na koniec sesji Claude aktualizuje ten plik.

Zasady:
- Commity po polsku, małe i opisowe. Każdą zmianę da się cofnąć w historii GitHuba.
- Zmiany w kodzie MIDI muszą dalej działać ze starym Web MIDI Browser (`forEach` zamiast `.values()`).
- Polskie nazwy nut w interfejsie: C, Cis, D, Dis, E, F, Fis, G, Gis, A, **B (= A#)**, **H (= B)**.
  W notacji `makeSong` używamy angielskich liter (B = H).

## Stan (11.11.2026)

Gotowe i działa:
- 6 wbudowanych utworów: Wlazł kotek, Panie Janie, Mrugaj gwiazdko, Oda do radości, Dla Elizy (początek, obie ręce), Gama C-dur.
- Wgrywanie plików MIDI z wyborem ścieżek (rąk).
- Tryby „Czekaj na mnie” i „W tempie” (25–150%), transpozycja, dźwięk z iPada, przewijanie, statystyki trafień.
- Klawiatura na ekranie, test świateł, przesunięcie świateł, diagnostyka i dziennik.
- Katalog utworów: wyszukiwanie w Wikimedia Commons, BitMidi i Lakh MIDI, pobieranie jednym kliknięciem, oznaczenie „Mam”, filtr „Tylko te, których nie mam”,
  podpowiedzi klasyczne i popowe, **🔊 Posłuchaj** przed pobraniem.
- Piosenki (wiele instrumentów): po otwarciu zaznaczona tylko melodia (⭐), przy ścieżkach nazwy instrumentów (np. „Lead 2 (sawtooth)”).
- Poziom trudności (Łatwe / Średnie / Trudne): filtr w katalogu (zapamiętany w ustawieniach) i plakietki przy wszystkich utworach.
  Biblioteki nie podają poziomu, więc liczymy go z nut. Progi sprawdzone na plikach z korpusu music21:
  pieśni ludowe → łatwe; chorał Bacha, arie, Dichterliebe → średnie; ragtime Joplina, Mozart K545, kwartety → trudne.
  Poziom dotyczy całego pliku – utwory z BitMidi z pełną aranżacją (wiele instrumentów) zwykle wychodzą jako trudne.

## Katalog utworów (biblioteki MIDI)

Aplikacja nie ma serwera, więc biblioteka musi pozwalać na pobieranie prosto z przeglądarki (nagłówki CORS).
Sprawdzone 11.11.2026 ze strony lukaszdomin.github.io:

| Biblioteka | Wyszukiwanie | Pobieranie pliku | Uwagi |
|---|---|---|---|
| Wikimedia Commons | ✅ `commons.wikimedia.org/w/api.php?...&origin=*`, `gsrsearch=filemime:audio/midi <zapytanie>` | ✅ `upload.wikimedia.org` | wolne licencje, głównie klasyka |
| BitMidi | ✅ `bitmidi.com/api/midi/search?q=&page=` (15 na stronę, `pageTotal`) | ✅ `bitmidi.com/uploads/<id>.mid` | >100 tys. plików od internautów, licencje niejasne |
| Lakh MIDI (clean) | ✅ u nas: `lakh.json` + szukanie w przeglądarce (20 na stronę) | ✅ `raw.githubusercontent.com/imsparsh/Lakh-MIDI-Dataset-Clean/<sha>/<Wykonawca>/<Tytuł>.mid` (CORS `*`) | 17 232 pliki, 2196 wykonawców, pop/rock/dance; zbiór C. Raffela CC-BY 4.0, pliki z internetu. Adres przypięty do commita `10c79f6`. Brak Better Off Alone. Część plików ma dziwnie długi czas (np. 75 min) – śmieci na końcu pliku |
| Mutopia Project | ❌ brak CORS | ❌ | |
| piano-midi.de | ❌ brak CORS (i tylko http) | ❌ | |

## Decyzje

- Aplikacja webowa zamiast natywnej aplikacji iOS: nie wymaga Maca, Xcode ani konta deweloperskiego Apple.
- Jeden plik HTML: prosto hostować i łatwo zmieniać z każdego urządzenia.
- Brak serwera: diagnostyka przez dziennik kopiowany do czatu.
- Lakh MIDI: spis nazw trzymamy u siebie (`lakh.json`), bo GitHub nie ma wyszukiwarki z CORS; samych plików nie kopiujemy –
  pobieramy je z cudzego repozytorium przez raw.githubusercontent.com, adresem przypiętym do commita (stabilne linki).
- Piosenki: domyślnie ćwiczymy samą melodię (wybraną automatycznie), resztę ścieżek dołącza się ręcznie.
  Fortepian na dwie ręce i utwory wbudowane – nadal wszystkie ścieżki.
- Nazwy instrumentów po angielsku (standard General MIDI), tak jak na stronach z plikami MIDI.
- Odsłuch tym samym prostym dźwiękiem co „Dźwięk z iPada” (bez bibliotek z próbkami instrumentów) – wystarcza, żeby ocenić, czy plik jest dobry.

## Do zrobienia / pomysły

(Łukasz decyduje o kolejności. Claude dopisuje tu pomysły, które padną w rozmowie.)
- [ ] Poziom liczony też dla pojedynczej ścieżki (np. sama melodia z piosenki z BitMidi), filtr poziomu w „Moje utwory”.
      Ważne teraz, gdy jest Lakh: prawie każda piosenka wychodzi „Trudne”, choć sama melodia (⭐) bywa łatwa.
- [ ] Sprawdzić na iPadzie odsłuch (przełącznik wyciszenia iPada wycisza Web Audio) i czy wybór melodii trafia na prawdziwych plikach.
- [ ] Zapamiętywać wybór ścieżek dla utworu (teraz po ponownym otwarciu wraca wybór automatyczny).
- [ ] Sprawdzić na iPadzie, czy BitMidi nie blokuje pobierania wielu plików naraz (kolejka poziomów pobiera wszystkie wyniki).
- [ ] Katalog: więcej bibliotek, jeśli znajdziemy takie z CORS (np. zbiory MIDI na GitHubie przez raw.githubusercontent.com).

## Dziennik zmian

- 11.11.2026: piosenki pop: automatyczny wybór ścieżki z melodią i nazwy instrumentów przy ścieżkach; podpowiedzi pop/dance w katalogu;
  biblioteka Lakh MIDI (`lakh.json`, `tools/lakh_index.py`); odsłuch przed pobraniem; smoke test serwuje stronę przez lokalny HTTP.
- 11.11.2026: poziom trudności utworów (łatwe/średnie/trudne): filtr w katalogu, plakietki w bibliotece, testy w `smoke_test.py`.
- 11.11.2026: katalog utworów z internetu (Wikimedia Commons + BitMidi), testy katalogu w `smoke_test.py`.
- 11.11.2026: pierwsza wersja; naprawa wykrywania urządzeń w Web MIDI Browser; diagnostyka, liczniki, dziennik, test nuty; potwierdzone działanie na iPadzie.
