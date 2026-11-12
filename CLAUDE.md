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
- „Start sesji” `F0 00 20 2B 69 00 00 55 F7` – potwierdzony w open-one-piano: bez niego keyboard nie słucha komend brzmienia (raz na połączenie).

**Brzmienie klawiszy** (open-one-piano, PROTOCOL.md i `assets/tones.json`, tabela `TOC` = The ONE COLOR):

| Akcja | Bajty |
|---|---|
| Włącz/wyłącz warstwę | `F0 00 20 2B 69 06 00 <warstwa> <0/1> F7` (warstwa 0 = to, co grają klawisze) |
| Brzmienie warstwy | `F0 00 20 2B 69 06 01 <warstwa> <bank MSB> <bank LSB> <program> F7` |
| Zapytaj o ustawienia | `F0 00 20 2B 69 1D 01 F7` → odpowiedź `… 5D 01 <dane> F7` (bajty 6, 7, 8: LSB, MSB, program warstwy 0) |

- Zwykłe Program Change na kanale 1 zmienia tylko brzmienie nut **przysłanych** z iPada – klawisze grają dalej swoim (sprawdzone 12.11.2026:
  w Pokazie wybrane brzmienia grały poprawnie, a klawisze, w które gra Łukasz – domyślnym brzmieniem keyboardu).
- Banki są własne dla modelu: COLOR włącza się z fortepianem **bank 16/0, program 0**. Para spoza listy → domyślny fortepian.

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
- Dane użytkownika: **lista pobranych utworów** (`id`, `title`, `src`, `url`, `lvl`, `roll`) i ustawienia w `localStorage` (`sk_songs`, `sk_settings`),
  **same pliki MIDI** (base64) w **IndexedDB** (baza `swiecace-klawisze`, magazyn `files`, klucz `song:<id>`; od 11.11.2026 –
  wcześniej pliki były w `sk_songs` i po zapełnieniu ~5 MB nowe utwory znikały po zamknięciu aplikacji).
  W pamięci sesji pliki są w `songBuf` (id → ArrayBuffer). `loadSongFiles()` przy starcie: wczytuje pliki z IndexedDB, przenosi stare wpisy
  z `u.b64` do IndexedDB (`storeSongFile()`), prosi o `navigator.storage.persist()`, zapisuje w dzienniku wpis „PAMIĘĆ: utworów …”,
  a brakujące pliki pobiera znowu (`ensureSongFile()` → `songUrl()`: zapisany `url` albo adres odtworzony z `src` dla Commons, BitMidi, Lakh, Billboard).
  Gdy IndexedDB nie działa, plik zostaje w liście (`u.b64`) jak dawniej. `openUser()` jest asynchroniczne (czeka na plik, gdy go nie ma w pamięci).
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
  - odtwarzacz: `prepare()` buduje `ns` (nuty, z siłą uderzenia `v` z pliku) i `steps` (grupy nut), tryby `wait`, `tempo` i `demo`
    (`timed()` = tryb z zegarem: `tempo` i `demo`);
  - **tryb „Pokaz”** (`S.mode = 'demo'`, 11.11.2026): aplikacja sama gra wybrane ścieżki – `loop()` wysyła do keyboardu zwykłe
    Note On / Note Off na kanale 1 (`demoNote()`, `demoOffs()`, brzmiące nuty w `demoOn`), więc gra on swoimi głośnikami;
    światła bez wyprzedzenia `LEAD` (razem z dźwiękiem), klawisze na ekranie wciśnięte (`.key.lit.press`), trafień nie liczymy,
    bez statystyk i okna wyniku. Pauza, przewijanie, koniec i wyjście → `demoSilence()` (Note Off + All Notes Off `B0 7B 00`).
    Bez keyboardu gra iPad (`tone()`). Wybór „Pokaz” w menu Opcje przełącza widok na wodospad. Tempo działa jak w „W tempie”.
    Kto gra Pokaz: `S.demoOut` (`'kbd'` keyboard / `'ipad'` – gra iPad, keyboard tylko świeci; `demoKbd()`), Ustawienia → „Pokaz gra” (`#demoOutSel`).
    Pokaz gra **brzmieniem utworu** (niżej);
  - **brzmienie dobrane do utworu** (11.11.2026): tabela `VOICES` (id → nazwa, program GM): `piano` Fortepian 0, `epiano` Pianino elektryczne 4,
    `pop` Syntezator pop 80, `synth` Syntezator dance 81, `organ` Organy 19, `harpsi` Klawesyn 6, `box` Pozytywka 10.
    `suggestVoice(s)` → `{v, why}` (zapamiętane w `s._vs`), po kolei: słowa w tytule z wykonawcą (`VOICE_KW`: kolędy i piosenki dla dzieci → pozytywka,
    toccata/hymn → organy, wykonawcy i słowa dance/techno/remix → syntezator dance, barok (Bach, Händel…) → klawesyn, klasyka fortepianowa → fortepian;
    podkreślenia z Lakh zamieniane na spacje), **rok przeboju z Billboard** (≥1980 pop, 1965–79 pianino elektryczne, wcześniej fortepian),
    **instrumenty w pliku** (tylko gdy plik ma zmiany programu albo perkusję): melodia na syntezatorze / ≥30% nut syntezatorów → dance (z perkusją i ≥118 BPM)
    albo pop; pianino elektryczne, organy, klawesyn, dzwonki; sam fortepian → fortepian; potem wykonawcy popu (`POP_KW`) → pop;
    perkusja + trochę syntezatorów → pop/dance; perkusja (zespół) → pianino elektryczne; na końcu fortepian. `parseMidi()` zwraca do tego
    `drums` (liczba nut perkusji), `bpm` (tempo na początku) i `progs` (czy plik ma zmiany programu); utwór ma `src` (`getUserSong()` / `addUserSong()`).
    `voiceOf(s)`: wybór Łukasza dla utworu (`S.songVoice[id]`) → propozycja (gdy `S.voice === 'auto'`) → fortepian (`S.voice === 'piano'`, „Zawsze fortepian”).
    **Keyboard**: `kbdVoice(force)` → `kbdProgram()` wysyła Bank Select i Program Change (`B0 00 <MSB>`, `B0 20 <LSB>`, `C0 <program>` – dla nut z iPada)
    i w kolejce `kbdQ` SysEx brzmienia klawiszy: start sesji (raz na połączenie, `kbdHello`), warstwa 0 wł., brzmienie warstwy 0, pytanie `1D 01`;
    odpowiedź czyta `kbdSettings()` (wpis „BRZMIENIE klawiszy (odpowiedź keyboardu)” – zgodne / INNE, w diagnostyce `D.kbdTone`).
    Bank/program dla COLOR w `VOICES[id].kbd` (fortepian 16/0/0, reszta bank 0). Wysyłane przy otwarciu utworu,
    zmianie brzmienia, Starcie (każdy tryb) i podłączeniu keyboardu; `kbdVoiceReset()` po powrocie do biblioteki → fortepian; ostatni program w `kbdProg`.
    `S.kbdMode`: `'song'` (przełączaj) / `'kbd'` (nie ruszaj – brzmienie wybrane na keyboardzie), Ustawienia → „Keyboard” (`#kbdModeSel`).
    **iPad**: `tone(n, dur, at, vol, dest, voice)` – fortepian próbkami, reszta `synthNote()` (WebAudio, nic nie pobiera): dance = 2 rozstrojone piły + filtr,
    pop = prostokąt + trójkąty, pianino elektryczne = FM, organy = 5 sinusów (16'…2'), klawesyn = piła z szybko gasnącym filtrem, pozytywka = sinusy.
    Głośności wyrównane do prostego trójkąta (pomiar przez OfflineAudioContext). Odsłuch w katalogu gra propozycją (`pv.voice`).
    **Menu Opcje → „Brzmienie utworu”** (`#voiceSeg`, `renderVoices()`, `setSongVoice()`): 7 przycisków, gwiazdka przy propozycji, pod spodem powód
    (`#voiceWhy`); stuknięcie zapisuje wybór dla utworu i gra krótki pasaż (na keyboardzie albo na iPadzie – tam, gdzie będzie słychać utwór);
    stuknięcie w propozycję usuwa wybór (wraca automat). Nazwa brzmienia (gdy nie fortepian) na przycisku Opcje. Usunięcie utworu czyści jego wybór.
    Ustawienia → „Brzmienie”: „Dobór brzmienia” (`#voiceSel`: dopasowane / zawsze fortepian), Keyboard, Pokaz gra, „Posłuchaj na iPadzie / na keyboardzie”.
    Stare ustawienia (`voice: 'piano'/'synth'`, `demoVoice`) przenoszone raz przy starcie (`voiceVer: 2`); dziennik: wpisy „BRZMIENIE:”;
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
    `tone()` gra próbką, gdy brzmienie to fortepian i próbki gotowe, inaczej trójkąt (zapas, póki się wczytują). Wszystko idzie przez `audioOut()` (kompresor).
    Próbki wczytują się zawsze przy pierwszym dźwięku. Stan w Ustawieniach → „Brzmienie” (`#pianoStatus`); dziennik: wpisy „FORTEPIAN:”;
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

## Stan (12.11.2026)

Gotowe i działa:
- 6 wbudowanych utworów: Wlazł kotek, Panie Janie, Mrugaj gwiazdko, Oda do radości, Dla Elizy (początek, obie ręce), Gama C-dur.
- Utwory MIDI z Katalogu z wyborem ścieżek (rąk). Ręczne wgrywanie plików usunięte – wcześniej wgrane pliki dalej są w bibliotece („własny plik”).
- Wygląd „Scena” w palecie „Noc” (granat i indygo; prawa ręka pomarańczowa, lewa niebieska – w tym kolorze świeci to, co zagrać). Osobny ekran biblioteki: „Graj dalej”, karty z miniaturą melodii
  i poziomem, filtr poziomu, „Edytuj” do usuwania, jedna wyszukiwarka dla własnych utworów i katalogu.
- Tryby „Czekaj na mnie”, „W tempie” (25–150%) i **„Pokaz”** (aplikacja sama gra utwór na keyboardzie, klawisze się wciskają, wodospad), transpozycja, dźwięk z iPada, przewijanie, statystyki trafień.
- Brzmienie fortepianu z nagranych próbek (pobierane raz, zapisane na iPadzie).
- **Brzmienie dobrane do utworu**: aplikacja proponuje brzmienie (syntezator do dance/techno i popu, pianino elektryczne do piosenek z zespołem,
  klawesyn do baroku, organy, pozytywka do kolęd i piosenek dla dzieci, fortepian do klasyki), a w menu Opcje można je zmienić dla każdego utworu.
  Keyboard przełącza się na to brzmienie (Program Change), iPad gra je syntezą.
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
- Dźwięk: fortepian z nagranych próbek, bez pobierania osobnych próbek basu, smyczków itd. (każde to kolejne 2–3 MB).
  (Wcześniej: tylko prosty dźwięk – Łukasz: „jak ze starej gry”.) Prosty trójkąt zostaje tylko jako zapas, póki próbki się wczytują
  (z Ustawień zniknął wybór „Prosty dźwięk” – 11.11.2026).
- Brzmienie dobrane do utworu (11.11.2026, Łukasz: „techniawka albo pop – nie klasyczny fortepian, tylko syntezator”):
  7 brzmień, każde = program General MIDI dla keyboardu + synteza WebAudio na iPadzie (bez pobierania). Propozycja z tytułu/wykonawcy,
  roku przeboju i instrumentów w pliku; wybór dla utworu w menu Opcje. Keyboard przełączamy też w trybach ćwiczenia (nie tylko w Pokazie),
  żeby Łukasz grał tym brzmieniem; po wyjściu do biblioteki wraca fortepian.
- Nowe hity: Lakh kończy się ok. 2010 r., BitMidi ma mało nowych piosenek. Jedyne znalezione źródło z CORS i nowymi przebojami to BiMMuDa –
  tylko top 5 z każdego roku i sama melodia, ale ręcznie spisana i łatwa do grania. Strony z dużą liczbą nowych MIDI (midishow, freemidi)
  nie mają CORS, a my nie mamy serwera.
- Próbki trzymamy w IndexedDB, nie w `localStorage` (za mały, ~5 MB).
- Pobrane utwory (11.11.2026, Łukasz: „znikają po zamknięciu”, jeden użytkownik, „najprościej jak się da”): pliki w IndexedDB, lista w `localStorage`,
  brakujące pliki pobierane znowu ze źródła. Bez serwera i bez kont. Zapis poza iPadem (np. plik w repozytorium przez API GitHuba)
  wymagałby tokenu trzymanego na iPadzie – odłożone, dopóki nie okaże się, że Web MIDI Browser czyści całą pamięć strony.

## Do zrobienia / pomysły

(Łukasz decyduje o kolejności. Claude dopisuje tu pomysły, które padną w rozmowie.)
- [ ] Sprawdzić na iPadzie zapis utworów: pobrać kilka utworów, zamknąć Web MIDI Browser (także przesunięciem w przełączniku aplikacji),
      otworzyć znowu. W dzienniku wpis „PAMIĘĆ: utworów N (z IndexedDB …, przeniesione z listy …, bez pliku …)” i „trwały zapis …”.
      Jeśli po zamknięciu znika **wszystko** (także ustawienia i fortepian pobiera się znowu) – Web MIDI Browser czyści pamięć strony
      i trzeba zapisywać listę poza iPadem (np. plik w repozytorium przez API GitHuba albo eksport/import listy).
- [ ] Sprawdzić „Pokaz” na iPadzie: czy keyboard gra nuty wysłane z iPada (ten sam test: Ustawienia → „Zagraj C na keyboardzie”),
      czy nie ma opóźnień / zawieszonych nut przez Bluetooth, czy keyboard nie odsyła granych nut jako wciśniętych (fioletowe klawisze).
      Jeśli keyboard nie gra – włączyć „Dźwięk z iPada”.
      **Potwierdzone 11.11.2026: keyboard gra nuty z iPada.** **Potwierdzone 12.11.2026: w Pokazie Program Change działa** (wybrane brzmienia grają poprawnie).
      Po zmianie z 12.11.2026 fortepian idzie jako bank 16 zamiast 0 – sprawdzić, czy Pokaz dalej gra fortepianem.
- [ ] Sprawdzić na iPadzie brzmienie klawiszy przez SysEx (12.11.2026): otworzyć utwór z syntezatorem, zagrać – czy klawisze grają syntezatorem;
      w dzienniku „BRZMIENIE klawiszy (odpowiedź keyboardu): … zgodne z wybranym”. Brak odpowiedzi → Web MIDI Browser może nie przepuszczać SysEx
      (sprawdzić „SysEx: tak” w diagnostyce). Po wyjściu do biblioteki klawisze wracają do fortepianu (16/0/0).
- [ ] Sprawdzić brzmienia na iPadzie i keyboardzie:
      czy programy 80/81 (syntezatory), 4, 6, 10, 19 brzmią sensownie na COLOR; jak brzmi synteza na iPadzie (głośność względem fortepianu);
      czy propozycje trafiają na prawdziwych utworach (Darude, ABBA, Bach, kolędy, hity Billboard).
- [ ] Pomysły do brzmień: więcej brzmień (gitara, smyczki, trąbka), ikona/nazwa brzmienia na karcie w bibliotece, propozycja brzmienia przy wynikach katalogu.
- [ ] Pomysł do „Pokazu”: przycisk na karcie utworu w bibliotece („Posłuchaj na keyboardzie”), granie całej aranżacji
      (wszystkie ścieżki) niezależnie od wybranych rąk, perkusja na kanale 10.
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

- 12.11.2026: klawiszami grało domyślne brzmienie keyboardu, a nie wybrane w aplikacji – Program Change działa tylko na nuty z iPada;
  teraz brzmienie klawiszy ustawia komenda SysEx keyboardu z open-one-piano (start sesji, warstwa 0, bank/program z listy COLOR),
  aplikacja pyta keyboard o ustawienia i zapisuje odpowiedź w dzienniku; fortepian COLOR = bank 16; testy w `smoke_test.py`.

- 11.11.2026: zapis pobranych utworów – pliki MIDI przeniesione z `localStorage` (~5 MB, po zapełnieniu nowe utwory znikały po zamknięciu)
  do IndexedDB; w `localStorage` zostaje sama lista; stare zapisy przenoszone przy starcie; brakujący plik pobierany znowu ze źródła;
  usuwanie kasuje też plik; wpis „PAMIĘĆ:” w dzienniku; testy w `smoke_test.py` (`storage_tests`, m.in. 12 plików po 450 KB).

- 11.11.2026: **brzmienie dobrane do utworu** – 7 brzmień (fortepian, pianino elektryczne, syntezator pop, syntezator dance, organy, klawesyn, pozytywka);
  aplikacja sama proponuje brzmienie (tytuł i wykonawca, rok przeboju, instrumenty, perkusja i tempo w pliku), a w menu Opcje można je zmienić
  dla każdego utworu (gwiazdka = propozycja); keyboard przełącza się na brzmienie utworu (Program Change) przy otwarciu i Starcie, po wyjściu wraca fortepian;
  iPad gra brzmienia syntezą; Ustawienia → „Brzmienie” (dopasowane / zawsze fortepian, przełączanie keyboardu, kto gra Pokaz) zamiast „Dźwięk z iPada” i „Pokaz”;
  testy w `smoke_test.py` (`voice_tests`).

- 11.11.2026: Pokaz: keyboard grał „dziwnym dźwiękiem” – przed Pokazem przełączamy jego brzmienie na fortepian (Bank Select + Program Change);
  w Ustawieniach wybór brzmienia Pokazu (fortepian, jasny fortepian, pianino elektryczne, klawesyn, organy, brzmienie z keyboardu,
  fortepian z iPada) i „Posłuchaj na keyboardzie”; testy w `smoke_test.py`.

- 11.11.2026: tryb **„Pokaz”** – aplikacja sama gra pobrany utwór na keyboardzie (Note On/Off, z siłą uderzenia z pliku),
  świecą diody, klawisze na ekranie się wciskają, nuty spływają w wodospadzie; pauza wycisza keyboard; bez keyboardu gra iPad;
  testy w `smoke_test.py` (`demo_tests`).

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
