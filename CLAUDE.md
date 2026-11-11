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
- `bimmuda.json` – spis hitów z Billboard Melodic Music Dataset (`[tytuł, wykonawca, rok, ścieżka]`, 375 utworów, 25 KB).
  Budowany skryptem `tools/bimmuda_index.py` z metadanych CSV repozytorium (duplikaty, np. Blinding Lights 2020/2021, usunięte).
- `swiecace-klawisze.html` przekierowuje do `./` (stary adres z zakładek).
- Hosting: **GitHub Pages** z gałęzi `main`, folder główny. Adres: https://lukaszdomin.github.io/pianino/
  Każdy push na `main` publikuje się w 1–2 minuty.
- Dane użytkownika (pobrane pliki MIDI jako base64, ustawienia) trzymamy w `localStorage` (`sk_songs`, `sk_settings`).
  Utwory z katalogu mają dodatkowe pole `src` (np. `commons:6596429`, `bitmidi:27978`, `billboard:2017/1/2017_01_full.mid`), po którym poznajemy, że już je mamy.
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
  - katalog utworów z internetu: obiekt `cat`, `catSearch()`, `catCommons()`, `catBitmidi()`, `catLakh()`, `catBillboard()`, `catDownload()`, `renderCatalog()`;
    spisy trzymane u nas (Lakh, Billboard) przeszukuje wspólne `idxFind()` (Billboard: przy równym dopasowaniu najnowsze najpierw);
    kolejność źródeł w „Wszystkie” = kolejność kluczy `CAT_FN` (Billboard pierwszy); przy wynikach Billboard „hit 2017 · sama melodia”;
    podpowiedzi `CAT_SUGG` w grupach (Klasyka, Nowe hity, Pop i rock, Dance i techno, Święta i dla dzieci);
  - odsłuch w katalogu: `catPreview()` / `pvTick()` / `pvStop()` – plik tylko w pamięci (`catA.buf`, więc „Pobierz” go nie ściąga drugi raz),
    pierwsze 30 s, melodia głośniej, tło max 6 dźwięków naraz, nuty planowane co 100 ms na 0,4 s do przodu; `tone()` przyjmuje czas, głośność i wyjście;
  - poziom trudności: `songLevel()` (punkty za tempo, akordy, rozpiętość, czarne klawisze, >4 ścieżki, długość; 0–2 łatwe, 3–5 średnie, 6+ trudne),
    w katalogu kolejka `catA` / `catPump()` pobiera pliki w tle (po 3 naraz) i liczy poziom; pobrany plik zostaje w pamięci dla „Pobierz”;
  - **dwa ekrany** (etap 3, 11.11.2026): **biblioteka** (`#home`, klasa `body.home`, ekran startowy, bez klawiatury)
    i **granie** (`#main` + `#view` + `#kbd`). `selectSong()` → `showPlay()`; „‹ Biblioteka” (`#backBtn`) → `goHome()`: zatrzymuje granie,
    zapisuje miejsce w `S.last = {id, step, total}`. Nagłówek wspólny: w bibliotece nazwa aplikacji + wyszukiwarka (`#libQ`),
    przy graniu „‹ Biblioteka” + tytuł (`#songTitle`) + statystyki; status i ustawienia zawsze;
  - biblioteka: `renderLib()`, `songCard()`, `songParts()`, `renderResume()`, `addUserSong()`, `removeUserSong()`.
    Kafelek **„Graj dalej”** (`#resume`, ostatni utwór z `S.last`, postęp, `#resumeBtn` wraca do tego kroku w trybie „Czekaj”).
    Pasek: „Twoje utwory”, filtr poziomu (`#libLvlSeg`, `S.libLvl`, zawsze widoczny), „Edytuj” (`#libEdit`, tylko gdy są pobrane),
    „Nowe utwory z katalogu” (`#openCatalog`). **Siatka kart** `#lib`: najpierw pobrane (`.song.user`, najnowsze na górze), potem
    wbudowane (`.song.builtin`). Karta: **miniatura melodii** (`rollOf()` – najwyższa nuta z pierwszych `ROLL_N` = 28 kroków domyślnych
    ścieżek, `rollSvg()`; dla pobranych zapisana w `u.roll`, starsze uzupełnia `rollOldSongs()` po 4 naraz), tytuł, wykonawca
    (z Lakh i Billboard odcięty z tytułu „Wykonawca – Tytuł”), **poziom kreskami** (`bars()`) i słowem, źródło. Usuwanie tylko w trybie „Edytuj”.
    **Jedna wyszukiwarka**: `#libQ` filtruje od razu (pobrane i wbudowane, `libNorm()`); pod siatką przycisk „Szukaj „…” w katalogu”
    (`#libFind`), a Enter, gdy nic nie pasuje, od razu przenosi zapytanie do Katalogu (`catFrom()`).
    **Ręcznego wgrywania plików nie ma** (usunięte 11.11.2026) – utwory dodaje tylko Katalog przez `addUserSong()`;
    smoke test też dodaje pliki przez `addUserSong()` i wraca do biblioteki przez `go_home()` / `open_catalog()`;
  - brzmienie fortepianu: `pianoLoad()` / `pianoNote()` / `pianoUI()` – próbki FluidR3 GM (`acoustic_grand_piano-mp3.js` z gleitz/midi-js-soundfonts,
    adres przypięty do commita `044fab8`, 88 nut A0–C8, 2,6 MB). Pobierane raz przy pierwszym dźwięku i zapisane w **IndexedDB**
    (baza `swiecace-klawisze`, magazyn `files`, klucz `PIANO_KEY`), bo GitHub daje `max-age=300`. Przy każdym uruchomieniu dekodowane
    po 4 naraz, zamieniane na mono i przycinane do `PIANO_SEC` (2,2 s) – pełne stereo to ~100 MB pamięci. Głośność `PIANO_GAIN` (12, próbki są ciche).
    `tone()` gra próbką, gdy `S.voice === 'piano'` i fortepian gotowy, inaczej trójkąt (zapas). Wszystko idzie przez `audioOut()` (kompresor).
    Ustawienia → „Dźwięk z iPada”: wybór brzmienia, stan, „Posłuchaj brzmienia”; dziennik: wpisy „FORTEPIAN:”;
  - dźwięk: `ensureAudio()` → `unlockAudio()` – iPad w trybie cichym wycisza WebAudio, więc przy stuknięciu ustawiamy
    `navigator.audioSession.type = 'playback'` i puszczamy ciche, zapętlone `<audio>` (WAV z `silentWav()`); stan w dzienniku („DŹWIĘK:”);
  - diagnostyka: `log()`, `diag()`, sekcja Dziennik w Ustawieniach z przyciskiem „Kopiuj dziennik”;
  - widok nut nad klawiaturą (`S.view`: `off` / `staff` / `fall`, przełącznik `#viewSeg`): jeden `<canvas id="viewCv">`,
    `renderView()` → `drawView()` (wołane z `renderKeys()` i z `loop()`; w trybie „Czekaj” płynne przesunięcie przez `vw.pos`).
    **Pięciolinia** `drawStaff()`: same główki nut w równych odstępach (kolumna = krok z `steps`), bez rytmu; obie pięciolinie
    na jednej skali (`dia()`: nuta → stopień, C4 na linii dodanej pośrodku), czarne klawisze jako krzyżyki; klucze 𝄞 𝄢 skalowane
    do pięciolinii (`clef()`), a gdy czcionka ich nie ma – litery G/F. Leży w `#right` (cała szerokość ekranu grania).
    **Wodospad** `drawFall()`: paski z `ns` spadają na klawisze, 3 s nad klawiaturą (`VIEW_SECS`, skalowane tempem); na całą
    szerokość (element `#view` przenoszony przed `#kbd`), położenie klawiszy z `keyGeom()` – to samo co klawiatura na ekranie.
    Kolory wodospadu (`FC`): **lewa ręka niebieska, prawa pomarańczowa** (ciemniejsze odcienie na czarnych klawiszach), aktualne
    jaśniejsze (`nowL` / `nowR`) z poświatą i białą obwódką (rysowane na końcu), trafione zielone, pomyłka różowo-czerwona;
    u góry wygaszanie do tła (pod odtwarzaczem).
    Ręka nuty (`n.h` w `ns`, `'L'`/`'R'`) z `hands()`: nazwa ścieżki (`HAND_L` / `HAND_R`: lewa/left/LH/bass, prawa/right/RH),
    przy kilku ścieżkach najwyższa = prawa, średnia < C4 = lewa (gdy wszystkie wysoko – najniższa lewa), jedna ścieżka z nutami
    po obu stronach C4 (15–85% poniżej) – podział na C4; sama melodia – cała prawa.
    **Układ wodospadu** (`body.fall`): wodospad na całą wysokość między tytułem a klawiaturą, odtwarzacz `#transport` przeniesiony
    do `#view` (u góry wodospadu), menu Opcje otwiera się wtedy w dół (`openOpts()` wybiera kierunek).
    **Linia trafienia** (`#felt` w `#kbd`, budowany w `buildKbd()`, odświeżany w `renderKeys()`): jasna kreska z poświatą nad klawiaturą,
    nad zapalonymi klawiszami świeci w kolorze ręki (we wszystkich widokach), na zielono po trafieniu.
    **Ręka zapalonych nut** na ekranie: `litHand` (nuta → `'L'`/`'R'`), ustawiana w `showStep()` z `steps[i].hands` (budowane w `prepare()`)
    i w `loop()` z `ns`; klawisz `.key.lit.lh` = lewa (niebieski), bez `lh` = prawa (pomarańczowy).
    Kolory pięciolinii (`VC`): przyszłe lawendowo-białe (coraz bledsze), aktualne **w kolorze ręki** z poświatą (`handCol()`)
    i **duża nazwa nuty nad kolumną** (zastępuje pole „Zagraj”), trafione zielone, pomyłka różowo-czerwona, minione przygaszone.
    Pięciolinia zostawia miejsce na nazwę u góry i na pływający odtwarzacz u dołu (`STAFF_TOP` / `STAFF_BOT`).
    W poziomie z widokiem klawiatura i widok mają po 22vh. Pole „Zagraj / potem” (`#now`) widać tylko w trybie „Bez nut” (`body.withView #now{display:none}`).
    Pięciolinia w `#right` rośnie i zajmuje całe wolne miejsce (`#right>#view{flex:1}`, główki do `half` = 11 px);
  - wygląd „Scena” (3 etapy, 11.11.2026; makiety: https://claude.ai/artifact/PsCLH8WKuvSDmZbxqmCrvp) w **palecie „Noc”** z wariantu C
    (od 11.11.2026, wcześniej czarny lakier z czerwienią – Łukasz: „smutny”): granat i indygo (zmienne CSS `--bg` #0f1131, `--panel`,
    `--panel2`, `--line`, `--text` = lawendowa biel), **kolory rąk** `--right` (pomarańczowy) i `--left` (niebieski), `--miss` (różowo-czerwony),
    `--blue` (fioletowy – wciśnięty klawisz bez nuty), `--ok` (zielony).
    Czcionki z Google Fonts: **Bricolage Grotesque** (tytuły, `--disp`) i **Atkinson Hyperlegible** (reszta i nazwy nut, `--ui`; czytelna z daleka).
    Zasada: **to, co trzeba zagrać teraz, świeci w kolorze ręki** (klawisz, linia trafienia, nuta, pasek); przyciski główne lawendowo-białe.
    **Cienie** delikatne, w odcieniu granatu (czarne brudzą paletę): zmienne `--sh-xs` / `--sh-sm` / `--sh-md` / `--sh-lg` (od przycisków
    po okna) i `--hl` (cienka jasna krawędź u góry, jak światło z góry); karty lekko się wciskają po stuknięciu; pod linią trafienia
    klawisze w cieniu (`#kbd::after`), czarne klawisze rzucają miękki cień na białe.
    Ikony to wbudowane SVG (`class="ico"`, w kodzie `ICO_PLAY`, `ICO_SEARCH`, `ICO_SPK`, `ICO_STOP`, `ICO_STAR`), **bez emoji** w całej aplikacji
    (także katalog i ustawienia; melodia w ścieżkach oznaczona gwiazdką SVG), bez napisów wielkimi literami. Klawiatura z głębią (gradienty, „krawędź” klawisza), nad nią linia trafienia,
    świecący klawisz w kolorze ręki z poświatą. Status: „Keyboard połączony” z kropką, nazwa urządzenia w `title`;
  - pasek odtwarzacza: pływająca „pigułka” `#transport` na dole prawej kolumny (`position:absolute` w `#right`): ⏮ Start/Pauza ⏭ ↺
    (same ikony, `playUI()` zmienia ikonę i `aria-label`) i przycisk **Opcje** (`#optsBtn`) z podsumowaniem słowami
    (`renderOpts()`: „Czekaj na mnie” / „W tempie 80%”, transpozycja, ikona głośnika, widok). Suwak `#pos` i krok są pod tytułem,
    statystyki („Trafione / Pomyłki”, `#stats`) obok tytułu. Menu `#opts` to pływający panel otwierany **w górę** od przycisku
    (`openOpts()` / `closeOpts()`): tryb, tempo, transpozycja, dźwięk z iPada, widok nut.
    Zamyka się stuknięciem obok, Escape i przy obrocie ekranu. Smoke test klika w menu przez `opt(page, selektor)`.

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
- Utwory MIDI z Katalogu z wyborem ścieżek (rąk). Ręczne wgrywanie plików usunięte – wcześniej wgrane pliki dalej są w bibliotece („własny plik”).
- Wygląd „Scena” w palecie „Noc” (granat i indygo; prawa ręka pomarańczowa, lewa niebieska – w tym kolorze świeci to, co zagrać). Osobny ekran biblioteki: „Graj dalej”, karty z miniaturą melodii
  i poziomem, filtr poziomu, „Edytuj” do usuwania, jedna wyszukiwarka dla własnych utworów i katalogu.
- Tryby „Czekaj na mnie” i „W tempie” (25–150%), transpozycja, dźwięk z iPada, przewijanie, statystyki trafień.
- Brzmienie fortepianu z nagranych próbek (pobierane raz, zapisane na iPadzie); prosty dźwięk do wyboru w Ustawieniach.
- Klawiatura na ekranie, test świateł, przesunięcie świateł, diagnostyka i dziennik.
- Pływający odtwarzacz: Start/Pauza, cofnij/dalej, od początku; suwak kroków pod tytułem; reszta opcji w menu „Opcje”.
- Widok nut nad klawiaturą do wyboru: „Bez nut”, „Nuty” (uproszczona pięciolinia z dużą nazwą aktualnej nuty) albo
  „Wodospad” (paski spadające na klawisze, kolory rąk). Domyślnie „Nuty”. Działa w obu trybach.
- Katalog utworów: wyszukiwanie w Wikimedia Commons, BitMidi, Lakh MIDI i **Hity (Billboard)** – melodie przebojów 1950–2024 (Ed Sheeran, Bieber, Weeknd, Dua Lipa…), pobieranie jednym kliknięciem, oznaczenie „Mam”, filtr „Tylko te, których nie mam”,
  podpowiedzi klasyczne i popowe, **Posłuchaj** przed pobraniem.
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
| Billboard (BiMMuDa) | ✅ u nas: `bimmuda.json` + `idxFind()` | ✅ `raw.githubusercontent.com/madelinehamilton/BiMMuDa/<sha>/bimmuda_dataset/<rok>/<miejsce>/<rok>_<miejsce>_full.mid` (CORS `*`) | ręcznie spisane **główne melodie** 5 największych singli roku z Billboard Year-End Hot 100, 1950–2024 (375 utworów; M. Hamilton i in., TISMIR 2024). Sama melodia, jedna ścieżka → 341 łatwe, 34 średnie. Miejsca bywają z literą (`2a`, `2b`). Adres przypięty do commita `d9b2222` |
| Mutopia Project | ❌ brak CORS | ❌ | |
| piano-midi.de | ❌ brak CORS (i tylko http) | ❌ | |
| shadowshahriar/midi (GitHub) | – | ✅ raw | tylko 37 plików, „pożyczone” z kanałów YouTube – nie dodane |
| NEXTLab-ZJU/popular-hook (Hugging Face) | ? | ? | refreny (hooki) nowych piosenek, nie całe utwory; nie sprawdzone (brak dostępu z sesji) |

## Decyzje

- Aplikacja webowa zamiast natywnej aplikacji iOS: nie wymaga Maca, Xcode ani konta deweloperskiego Apple.
- Jeden plik HTML: prosto hostować i łatwo zmieniać z każdego urządzenia.
- Brak serwera: diagnostyka przez dziennik kopiowany do czatu.
- Lakh MIDI: spis nazw trzymamy u siebie (`lakh.json`), bo GitHub nie ma wyszukiwarki z CORS; samych plików nie kopiujemy –
  pobieramy je z cudzego repozytorium przez raw.githubusercontent.com, adresem przypiętym do commita (stabilne linki).
- Piosenki: domyślnie ćwiczymy samą melodię (wybraną automatycznie), resztę ścieżek dołącza się ręcznie.
  Fortepian na dwie ręce i utwory wbudowane – nadal wszystkie ścieżki.
- Nazwy instrumentów po angielsku (standard General MIDI), tak jak na stronach z plikami MIDI.
- Nuty bez wartości rytmicznych (same główki w równych odstępach): MIDI nie mówi, czy to ćwierćnuta czy ósemka,
  a pełny zapis (takty, belki, pauzy) wymagałby odtwarzania rytmu i biblioteki do nut – dużo pracy, słabe wyniki na piosenkach z Lakh.
- Dźwięk: fortepian z nagranych próbek dla wszystkiego (odsłuch i „Dźwięk z iPada”), bez osobnych brzmień basu, smyczków itd.
  (każde to kolejne 2–3 MB). Prosty syntezator zostaje jako zapas i do wyboru w Ustawieniach. (Wcześniej: tylko prosty dźwięk – Łukasz: „jak ze starej gry”.)
- Nowe hity: Lakh kończy się ok. 2010 r., BitMidi ma mało nowych piosenek. Jedyne znalezione źródło z CORS i nowymi przebojami to BiMMuDa –
  tylko top 5 z każdego roku i sama melodia, ale ręcznie spisana i łatwa do grania. Strony z dużą liczbą nowych MIDI (midishow, freemidi)
  nie mają CORS, a my nie mamy serwera.
- Próbki trzymamy w IndexedDB, nie w `localStorage` (za mały, ~5 MB, i są tam już pobrane utwory).

## Do zrobienia / pomysły

(Łukasz decyduje o kolejności. Claude dopisuje tu pomysły, które padną w rozmowie.)
- [ ] Sprawdzić etap 3 na iPadzie: przewijanie siatki palcem, „Graj dalej” po zamknięciu i ponownym otwarciu Web MIDI Browser,
      szukanie z klawiaturą ekranową (Enter → katalog), czas pierwszego otwarcia przy wielu pobranych utworach (miniatury `rollOldSongs()`).
- [ ] Pomysł: katalog też jako pełny ekran w stylu biblioteki (teraz okno nad biblioteką), karty wyników z miniaturą po odsłuchu.
- [ ] Sprawdzić etap 2 na iPadzie: czy kolory rąk trafiają na prawdziwych plikach (fortepian w jednej ścieżce, piosenki z Lakh),
      czy wodospad jest płynny na całej wysokości.
- [ ] Sprawdzić etap 1 na iPadzie: czy czcionki z Google Fonts się wczytują w Web MIDI Browser, czytelność dużej nazwy nuty z pulpitu,
      czy pływający odtwarzacz nie zasłania nut w pionie i w poziomie.
- [ ] Poziom liczony też dla pojedynczej ścieżki (np. sama melodia z piosenki z BitMidi). (Filtr poziomu w „Moje utwory” już jest – na razie po poziomie całego pliku).
      Ważne teraz, gdy jest Lakh: prawie każda piosenka wychodzi „Trudne”, choć sama melodia (⭐) bywa łatwa.
- [ ] Sprawdzić na iPadzie, czy po poprawce odsłuch gra (wpis „DŹWIĘK:” w dzienniku) i czy wybór melodii trafia na prawdziwych plikach.
- [ ] Sprawdzić na iPadzie fortepian: czas wczytywania (wpis „FORTEPIAN: gotowy … dekodowanie … ms”), głośność względem dawnego dźwięku,
      czy po zamknięciu Web MIDI Browser próbki zostają (wpis „z pamięci iPada”).
- [ ] Pomysł: osobne brzmienia dla basu/smyczków/syntezatorów w odsłuchu (pobierane na żądanie, jak fortepian).
- [ ] Zapamiętywać wybór ścieżek dla utworu (teraz po ponownym otwarciu wraca wybór automatyczny).
- [ ] Sprawdzić na iPadzie, czy BitMidi nie blokuje pobierania wielu plików naraz (kolejka poziomów pobiera wszystkie wyniki).
- [ ] Katalog: więcej bibliotek, jeśli znajdziemy takie z CORS (np. zbiory MIDI na GitHubie przez raw.githubusercontent.com).
      Nowych hitów nadal mało (Billboard = 5 na rok). Do sprawdzenia: popular-hook na Hugging Face (refreny), BitMidi na iPadzie dla nowych tytułów.
- [ ] Sprawdzić na iPadzie Hity (Billboard): czy melodia brzmi dobrze w odsłuchu i czy zakres (czasem niski, np. Love Yourself B2–B3) mieści się na keyboardzie.
- [ ] Sprawdzić widok nut na iPadzie: czy klucze 𝄞 𝄢 dobrze siedzą na pięciolinii, czy przewijanie jest płynne
      przy długich piosenkach i czy w poziomie wszystko się mieści (pole „Zagraj”, lista utworów).
- [ ] Pomysły do widoku nut: nazwy nut na wszystkich główkach (nie tylko aktualnych), kreski taktowe, gdy plik ma metrum,
      bemole zamiast krzyżyków w tonacjach bemolowych, regulacja wysokości widoku / szybkości wodospadu.

## Dziennik zmian

- 11.11.2026: delikatne cienie w odcieniu granatu: karty, „Graj dalej”, nagłówek, przyciski, odtwarzacz, menu, okna, klawiatura
  (cień pod linią trafienia, czarne klawisze rzucają cień); karty lekko się wciskają po stuknięciu.

- 11.11.2026: paleta „Noc” zamiast czarnej (Łukasz: czerń „smutna”, lepszy granat z wariantu C): granatowe tło i panele, lawendowa biel;
  to, co zagrać, świeci w kolorze ręki (prawa pomarańczowa, lewa niebieska) – klawisze, nuty na pięciolinii, paski wodospadu;
  zamiast bordowego filcu jasna linia trafienia z poświatą; pomyłki różowo-czerwone; test kolorów rąk na klawiszach w `smoke_test.py`.

- 11.11.2026: nowy wygląd „Scena”, etap 3 – osobny ekran biblioteki zamiast lewego panelu: „Graj dalej” (ostatni utwór i krok),
  siatka kart z miniaturą melodii, poziomem kreskami i źródłem, filtr poziomu zawsze widoczny, jedna wyszukiwarka (biblioteka + „Szukaj w katalogu”),
  ekran grania na całą szerokość z „‹ Biblioteka”; usunięty wysuwany panel z etapu 2; emoji w katalogu i ustawieniach zamienione na ikony SVG,
  bez napisów wielkimi literami; testy biblioteki przepisane w `smoke_test.py`.

- 11.11.2026: nowy wygląd „Scena”, etap 2 – wodospad: kolory rąk (lewa jasnoniebieska, prawa kremowa, `hands()`), aktualne paski czerwone
  ze świeceniem, wygaszanie u góry, wodospad na całą wysokość, odtwarzacz u góry wodospadu, lista utworów jako wysuwany panel „Utwory”,
  świecący filc nad zapalonymi klawiszami; testy rąk i układu wodospadu w `smoke_test.py`.

- 11.11.2026: nowe źródło w katalogu **Hity (Billboard)** – melodie 5 największych przebojów każdego roku 1950–2024 z BiMMuDa
  (`bimmuda.json`, `tools/bimmuda_index.py`); podpowiedzi „Nowe hity” (Ed Sheeran, Justin Bieber, Taylor Swift…); testy w `smoke_test.py`.

- 11.11.2026: nowy wygląd „Scena”, etap 1 – ekran grania: kolory lakieru pianina, czcionki Bricolage Grotesque + Atkinson Hyperlegible,
  ikony SVG zamiast emoji, ciemna pięciolinia z czerwoną aktualną nutą i dużą nazwą nuty (zamiast pola „Zagraj”), pływający odtwarzacz,
  klawiatura z głębią i filcowym paskiem, pomyłki na bursztynowo; testy odtwarzacza i nowych kolorów w `smoke_test.py`.

- 11.11.2026: brzmienie fortepianu z nagranych próbek (FluidR3 GM) zamiast dźwięku „jak ze starej gry” – w odsłuchu i „Dźwięku z iPada”;
  pobierane raz, zapisane w IndexedDB; wybór brzmienia i stan w Ustawieniach; testy z podstawioną paczką próbek.
- 11.11.2026: zwarty pasek odtwarzacza – tryb, tempo, transpozycja, dźwięk z iPada i widok nut przeniesione do menu „🎚 Opcje”
  (na przycisku podsumowanie ikonami); pięciolinia zajmuje zwolnione miejsce; testy menu w `smoke_test.py`.

- 11.11.2026: widok nut nad klawiaturą – do wyboru pięciolinia (aktualne nuty na pomarańczowo, trafione na zielono,
  pomyłki na czerwono) albo wodospad (paski spadające na klawisze); przełącznik „Bez nut / Nuty / Wodospad”; testy w `smoke_test.py`.

- 11.11.2026: naprawa odsłuchu na iPadzie – czas leciał, ale nie było dźwięku (tryb cichy wycisza WebAudio); odblokowanie sesji dźwięku, wpis „DŹWIĘK:” w dzienniku.

- 11.11.2026: wygląd: usunięte ręczne wgrywanie plików MIDI; nowy lewy panel (Katalog na górze, jedna przewijana lista – wcześniej
  w poziomie „Moje utwory” miały 8 px i nic nie było widać; najnowsze na górze; dwie linie w wierszu; zwijane wbudowane; „Edytuj” → „Usuń”;
  wyszukiwanie i filtr poziomu od 10 utworów); testy panelu w `smoke_test.py`.

- 11.11.2026: piosenki pop: automatyczny wybór ścieżki z melodią i nazwy instrumentów przy ścieżkach; podpowiedzi pop/dance w katalogu;
  biblioteka Lakh MIDI (`lakh.json`, `tools/lakh_index.py`); odsłuch przed pobraniem; smoke test serwuje stronę przez lokalny HTTP.
- 11.11.2026: poziom trudności utworów (łatwe/średnie/trudne): filtr w katalogu, plakietki w bibliotece, testy w `smoke_test.py`.
- 11.11.2026: katalog utworów z internetu (Wikimedia Commons + BitMidi), testy katalogu w `smoke_test.py`.
- 11.11.2026: pierwsza wersja; naprawa wykrywania urządzeń w Web MIDI Browser; diagnostyka, liczniki, dziennik, test nuty; potwierdzone działanie na iPadzie.
